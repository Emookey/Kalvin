# SPDX-License-Identifier: AGPL-3.0-or-later
"""Schema, semantic, cross-reference, and policy validation."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .graph import find_cycle
from .loader import load_architecture
from .models import Architecture, ValidationResult


EXPECTED_PROFILES = {"lab", "core", "storage"}
EXPECTED_STATE_CLASSES = {"AUTHORITATIVE", "DERIVED", "EPHEMERAL", "CONFIGURATION", "SECRET", "LOG"}
EXPECTED_BACKUP_CLASSES = {"REQUIRED", "REBUILDABLE", "EXCLUDED"}
EXPECTED_DEPENDENCY_KINDS = {"STARTUP", "HEALTH", "READINESS", "OPTIONAL_INTEGRATION"}
EXPECTED_EXPOSURES = {"PROCESS_LOCAL", "HOST_INTERNAL", "PLATFORM_INTERNAL", "LAN", "OVERLAY", "PUBLIC"}
EXPECTED_PRIVILEGES = {
    "UNPRIVILEGED_APPLICATION",
    "LIMITED_PLATFORM_SERVICE",
    "HOST_ADMINISTRATIVE",
    "EXTERNAL_HOST_MANAGEMENT",
}
EXPECTED_CONFIGURATION_LAYERS = [
    "REPOSITORY_SAFE_DEFAULTS",
    "PROFILE_CONFIGURATION",
    "HOST_LOCAL_CONFIGURATION",
    "DESIGNATED_GENERATED_VALUES",
]
DECLARATIVE_VERIFIABLE_GATES = {
    "platform.contracts-valid",
    "repositories.resolved",
    "identity.separation-validated",
    "exposure.policy-valid",
}


def _duplicates(values: Iterable[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _walk_strings(value: Any, location: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield location, value
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from _walk_strings(value[key], f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{location}[{index}]")


def sensitive_value_reason(value: str) -> str | None:
    """Detect credential-like material without trying to resolve a secret."""
    private_marker = "-----BEGIN " + "PRIVATE KEY-----"
    if private_marker in value or ("-----BEGIN " in value and " PRIVATE KEY-----" in value):
        return "private-key-looking material"
    if re.search(r"[a-z][a-z0-9+.-]*://[^/@\s:]+:[^/@\s]+@", value, re.IGNORECASE):
        return "credential-bearing URL"
    if re.search(r"\b(?:ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{10,}\b", value):
        return "token-looking material"
    if re.search(r"\b(?:password|passwd|api[_-]?key|token)\s*[:=]\s*[^\s,;]+", value, re.IGNORECASE):
        return "secret-looking assignment"
    return None


def legacy_runtime_path(value: str) -> bool:
    if not value.startswith("/"):
        return False
    lowered = value.lower()
    legacy_parts = ("/" + "goodwill", "/" + "odysseus" + "-ai", "/" + "mbc" + "-intelligence")
    return any(part in lowered for part in legacy_parts)


def _schema_location(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return "$" + "".join(f"[{part}]" if part.isdigit() else f".{part}" for part in parts)


def _network_ref_locations(value: Any, location: str = "$") -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if key == "$ref" and isinstance(child, str) and child.lower().startswith(("http://", "https://")):
                yield child_location
            yield from _network_ref_locations(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _network_ref_locations(child, f"{location}[{index}]")


def validate_schemas(architecture: Architecture, result: ValidationResult) -> None:
    schema_ids: list[str] = []
    for name, schema in sorted(architecture.schemas.items()):
        location = f"schemas/{name}"
        schema_id = schema.get("$id")
        if isinstance(schema_id, str):
            schema_ids.append(schema_id)
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            result.add("SCHEMA ERROR", "invalid-schema", location, exc.message)
        for ref_location in _network_ref_locations(schema):
            result.add(
                "POLICY ERROR",
                "network-schema-reference",
                f"{location}:{ref_location}",
                "remote schema references are forbidden; schemas must resolve locally and offline",
            )
    for duplicate in _duplicates(schema_ids):
        result.add("SCHEMA ERROR", "duplicate-schema-id", "schemas", f"duplicate $id {duplicate!r}")

    documents: list[tuple[str, dict[str, Any], Path]] = []
    for name, document in sorted(architecture.catalogs.items()):
        documents.append((f"manifests/{name}", document, architecture.document_paths[f"catalog:{name}"]))
    for name, document in sorted(architecture.profiles.items()):
        documents.append((f"deploy/profiles/{name}", document, architecture.document_paths[f"profile:{name}"]))

    for label, document, document_path in documents:
        schema_ref = document.get("$schema")
        if not isinstance(schema_ref, str):
            result.add("SCHEMA ERROR", "missing-schema-ref", label, "declaration has no string $schema")
            continue
        resolved = (document_path.parent / schema_ref).resolve()
        try:
            relative = resolved.relative_to(architecture.root)
        except ValueError:
            result.add("SCHEMA ERROR", "schema-path-escape", label, f"schema path escapes repository: {schema_ref}")
            continue
        schema = architecture.schemas.get(resolved.name)
        if schema is None or relative.parent != Path("schemas"):
            result.add("SCHEMA ERROR", "unknown-local-schema", label, f"local schema does not exist: {schema_ref}")
            continue
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(document), key=lambda item: (list(item.absolute_path), item.message))
        for error in errors:
            result.add("SCHEMA ERROR", "schema-validation", f"{label}:{_schema_location(error)}", error.message)


def _validate_vocabularies(architecture: Architecture, result: ValidationResult) -> None:
    vocab = architecture.catalogs["vocabularies"]
    exact_sets = (
        ("state_classes", {item["id"] for item in vocab["state_classes"]}, EXPECTED_STATE_CLASSES),
        ("backup_classes", set(vocab["backup_classes"]), EXPECTED_BACKUP_CLASSES),
        ("exposure_classes", set(vocab["exposure_classes"]), EXPECTED_EXPOSURES),
        ("privilege_classes", set(vocab["privilege_classes"]), EXPECTED_PRIVILEGES),
        ("dependency_kinds", set(vocab["dependency_kinds"]), EXPECTED_DEPENDENCY_KINDS),
        ("profile_requirements", set(vocab["profile_requirements"]), {"REQUIRED", "OPTIONAL", "FORBIDDEN"}),
    )
    for name, actual, expected in exact_sets:
        if actual != expected:
            result.add("POLICY ERROR", "vocabulary-drift", f"manifests/vocabularies.json:{name}", f"expected {sorted(expected)}, got {sorted(actual)}")
    if vocab.get("configuration_source_layers") != EXPECTED_CONFIGURATION_LAYERS:
        result.add(
            "POLICY ERROR",
            "configuration-precedence",
            "manifests/vocabularies.json:configuration_source_layers",
            "configuration precedence must remain repository defaults -> profile -> host-local -> generated",
        )


def _validate_components(architecture: Architecture, result: ValidationResult) -> None:
    vocab = architecture.catalogs["vocabularies"]
    components = architecture.catalogs["components"]["components"]
    repositories = architecture.catalogs["repositories"]["repositories"]
    gates = architecture.catalogs["readiness-gates"]["gates"]
    component_ids = [item["id"] for item in components]
    component_id_set = set(component_ids)
    repository_ids = {item["id"] for item in repositories}
    gate_ids = {item["id"] for item in gates}
    state_classes = {item["id"] for item in vocab["state_classes"]}
    backup_classes = set(vocab["backup_classes"])
    identity_classes = set(vocab["identity_classes"])
    config_layers = set(vocab["configuration_source_layers"])
    conflict_policies = set(vocab["configuration_conflict_policies"])

    for duplicate in _duplicates(component_ids):
        result.add("SEMANTIC ERROR", "duplicate-component", "manifests/components.json", f"duplicate component identity {duplicate!r}")

    relationship_edges: dict[str, list[tuple[str, str]]] = {kind: [] for kind in EXPECTED_DEPENDENCY_KINDS}
    for component in components:
        component_id = component["id"]
        if component["identity_class"] not in identity_classes:
            result.add("SEMANTIC ERROR", "unknown-identity-class", component_id, f"unknown identity class {component['identity_class']!r}")
        if component["privilege_class"] not in EXPECTED_PRIVILEGES:
            result.add("SEMANTIC ERROR", "unknown-privilege", component_id, f"unknown privilege class {component['privilege_class']!r}")
        if component["health_gate"] not in gate_ids:
            result.add("CROSS-REFERENCE ERROR", "unknown-health-gate", component_id, f"unknown health gate {component['health_gate']!r}")
        for gate in component["readiness_gates"]:
            if gate not in gate_ids:
                result.add("CROSS-REFERENCE ERROR", "unknown-readiness-gate", component_id, f"unknown readiness gate {gate!r}")
        if component["exposure"]["default"] not in component["exposure"]["allowed"]:
            result.add("POLICY ERROR", "default-exposure-not-allowed", component_id, "default exposure is outside component allowlist")
        for dependency in component["dependencies"]:
            target = dependency["component"]
            kind = dependency["kind"]
            if target not in component_id_set:
                result.add("CROSS-REFERENCE ERROR", "missing-dependency", component_id, f"dependency {target!r} is not in the component catalog")
            elif kind in relationship_edges:
                relationship_edges[kind].append((target, component_id))
        version = component["version"]
        if version["source"] == "REPOSITORY_LOCK" and version["repository_id"] not in repository_ids:
            result.add("CROSS-REFERENCE ERROR", "unknown-repository", component_id, f"repository {version['repository_id']!r} is not declared")
        if version["source"] == "IMPLEMENTATION_LOCK" and version["repository_id"] is not None:
            result.add("SEMANTIC ERROR", "implementation-repository-mismatch", component_id, "implementation lock must not claim a repository ID")

        state_ids = [item["id"] for item in component["state_requirements"]]
        for duplicate in _duplicates(state_ids):
            result.add("SEMANTIC ERROR", "duplicate-state-id", component_id, f"duplicate state identity {duplicate!r}")
        for item in component["state_requirements"]:
            state_class = item["class"]
            backup = item["backup"]
            justification = item.get("policy_justification")
            location = f"{component_id}.{item['id']}"
            if state_class not in state_classes:
                result.add("SEMANTIC ERROR", "unknown-state-class", location, f"unknown state class {state_class!r}")
            if backup not in backup_classes:
                result.add("SEMANTIC ERROR", "unknown-backup-class", location, f"unknown backup class {backup!r}")
            if state_class == "AUTHORITATIVE" and backup != "REQUIRED" and not justification:
                result.add("POLICY ERROR", "authoritative-backup", location, "authoritative state requires backup REQUIRED unless explicitly justified")
            if state_class == "DERIVED" and backup == "REQUIRED":
                result.add("POLICY ERROR", "derived-promoted-to-authority", location, "derived state cannot be the required authoritative recovery source")
            if state_class == "EPHEMERAL" and backup == "REQUIRED" and not justification:
                result.add("POLICY ERROR", "ephemeral-required-backup", location, "ephemeral state cannot require backup without explicit justification")
            if legacy_runtime_path(item["path"]):
                result.add("POLICY ERROR", "legacy-runtime-path", location, "legacy GoodWill/Odysseus/MBC runtime paths are forbidden")

        config_ids = [item["id"] for item in component["configuration_requirements"]]
        for duplicate in _duplicates(config_ids):
            result.add("SEMANTIC ERROR", "duplicate-configuration-id", component_id, f"duplicate configuration identity {duplicate!r}")
        for item in component["configuration_requirements"]:
            if item["source_layer"] not in config_layers:
                result.add("SEMANTIC ERROR", "unknown-configuration-layer", component_id, f"unknown source layer {item['source_layer']!r}")
            if item["conflict_policy"] not in conflict_policies:
                result.add("SEMANTIC ERROR", "unknown-conflict-policy", component_id, f"unknown conflict policy {item['conflict_policy']!r}")

        secret_ids = [item["id"] for item in component["secret_references"]]
        for duplicate in _duplicates(secret_ids):
            result.add("SEMANTIC ERROR", "duplicate-secret-reference", component_id, f"duplicate secret reference {duplicate!r}")

    for kind in ("STARTUP", "HEALTH", "READINESS"):
        cycle = find_cycle(component_id_set, relationship_edges[kind])
        if cycle:
            result.add("SEMANTIC ERROR", "dependency-cycle", f"dependencies.{kind}", f"cycle: {' -> '.join(cycle)}")


def _validate_profiles(architecture: Architecture, result: ValidationResult) -> None:
    components = architecture.catalogs["components"]["components"]
    component_by_id = {item["id"]: item for item in components}
    component_ids = set(component_by_id)
    gates = architecture.catalogs["readiness-gates"]["gates"]
    gate_ids = {item["id"] for item in gates}
    exposure_order = architecture.catalogs["vocabularies"]["exposure_classes"]
    exposure_rank = {name: index for index, name in enumerate(exposure_order)}

    actual_profile_ids = {profile["id"] for profile in architecture.profiles.values()}
    if actual_profile_ids != EXPECTED_PROFILES:
        result.add("POLICY ERROR", "profile-set", "deploy/profiles", f"exact profiles must be {sorted(EXPECTED_PROFILES)}; got {sorted(actual_profile_ids)}")

    for filename_id, profile in sorted(architecture.profiles.items()):
        profile_id = profile["id"]
        if profile_id != filename_id:
            result.add("SEMANTIC ERROR", "profile-file-mismatch", f"deploy/profiles/{filename_id}.json", f"declares profile {profile_id!r}")
        selections = profile["components"]
        selected_ids = [item["id"] for item in selections]
        for duplicate in _duplicates(selected_ids):
            result.add("SEMANTIC ERROR", "duplicate-profile-component", profile_id, f"component {duplicate!r} appears more than once")
        unknown = sorted(set(selected_ids) - component_ids)
        missing = sorted(component_ids - set(selected_ids))
        for item in unknown:
            result.add("CROSS-REFERENCE ERROR", "unknown-component", profile_id, f"unknown component {item!r}")
        for item in missing:
            result.add("CROSS-REFERENCE ERROR", "profile-component-missing", profile_id, f"component {item!r} is absent from profile")
        for gate in profile["required_readiness_gates"]:
            if gate not in gate_ids:
                result.add("CROSS-REFERENCE ERROR", "unknown-readiness-gate", profile_id, f"unknown readiness gate {gate!r}")
        for selection in selections:
            component = component_by_id.get(selection["id"])
            if component is None:
                continue
            expected = component["default_requirement_by_profile"][profile_id]
            if selection["requirement"] != expected:
                result.add("SEMANTIC ERROR", "profile-catalog-mismatch", f"{profile_id}.{selection['id']}", f"profile says {selection['requirement']}; catalog says {expected}")
            if selection["default_enabled"] != (selection["requirement"] == "REQUIRED"):
                result.add("POLICY ERROR", "unsafe-component-default", f"{profile_id}.{selection['id']}", "only REQUIRED components may be enabled by default")
            allowed = profile_id in component["allowed_profiles"]
            if allowed == (selection["requirement"] == "FORBIDDEN"):
                result.add("POLICY ERROR", "profile-allowlist-mismatch", f"{profile_id}.{selection['id']}", "profile requirement and component allowed_profiles disagree")
            default_exposure = component["exposure"]["default"]
            ceiling = profile["default_exposure_ceiling"]
            exceptions = {item["component"]: item for item in profile["exposure_exceptions"]}
            if (
                selection["requirement"] != "FORBIDDEN"
                and exposure_rank[default_exposure] > exposure_rank[ceiling]
                and selection["id"] not in exceptions
            ):
                result.add("POLICY ERROR", "exposure-ceiling", f"{profile_id}.{selection['id']}", f"default {default_exposure} exceeds profile ceiling {ceiling}")
        for exception in profile["exposure_exceptions"]:
            if exception["component"] not in component_by_id:
                result.add("CROSS-REFERENCE ERROR", "unknown-exposure-component", profile_id, f"unknown component {exception['component']!r}")
            for gate in exception["requires_gates"]:
                if gate not in gate_ids:
                    result.add("CROSS-REFERENCE ERROR", "unknown-exposure-gate", profile_id, f"unknown gate {gate!r}")

    by_id = {item["id"]: item for item in architecture.profiles.values()}
    if EXPECTED_PROFILES <= set(by_id):
        lab, core, storage = by_id["lab"], by_id["core"], by_id["storage"]
        selections = {name: {item["id"]: item for item in profile["components"]} for name, profile in by_id.items()}
        if "kal.rag-status-durable" not in core["required_readiness_gates"]:
            result.add("POLICY ERROR", "core-rag-gate", "core", "kal.rag-status-durable is a mandatory Core gate")
        if selections["core"]["backup-client"]["requirement"] != "REQUIRED" or selections["core"]["storage-backup-target"]["requirement"] != "FORBIDDEN":
            result.add("POLICY ERROR", "core-storage-boundary", "core", "Core requires outbound backup-client and must not own storage retention")
        for component_id in ("kal", "beepy", "model-runtime"):
            if selections["storage"][component_id]["requirement"] != "FORBIDDEN":
                result.add("POLICY ERROR", "storage-application-compute", "storage", f"{component_id} must be forbidden on Storage")
        if selections["storage"]["storage-backup-target"]["requirement"] != "REQUIRED":
            result.add("POLICY ERROR", "storage-retention", "storage", "storage-backup-target must be required")
        if selections["lab"]["public-test-exposure"]["default_enabled"]:
            result.add("POLICY ERROR", "public-default", "lab", "public-test-exposure must remain default-off")
        if core["exposure_exceptions"] or storage["exposure_exceptions"]:
            result.add("POLICY ERROR", "production-public-exception", "deploy/profiles", "Core and Storage may not define exposure exceptions")


def _validate_policy(architecture: Architecture, result: ValidationResult) -> None:
    components = architecture.catalogs["components"]["components"]
    by_id = {item["id"]: item for item in components}
    repositories = architecture.catalogs["repositories"]
    compatibility = architecture.catalogs["compatibility"]
    gates = architecture.catalogs["readiness-gates"]["gates"]

    for component in components:
        if component["privilege_class"] in {"HOST_ADMINISTRATIVE", "EXTERNAL_HOST_MANAGEMENT"}:
            result.add("POLICY ERROR", "administrative-component", component["id"], "Phase 4D components may not receive host-administrative or RMM privilege")
        if component["id"] in {"kal", "beepy"} and component["identity_class"] in {"PLATFORM_ADMINISTRATION", "FUTURE_RMM"}:
            result.add("POLICY ERROR", "application-identity-escalation", component["id"], "application identity may not inherit platform administration or RMM")
        if "PUBLIC" in component["exposure"]["allowed"] and component["id"] != "public-test-exposure":
            result.add("POLICY ERROR", "implicit-public-service", component["id"], "only the explicit lab public-test component may permit PUBLIC exposure")

    model = by_id.get("model-runtime")
    if model and (model["version"]["source"] != "IMPLEMENTATION_LOCK" or model["version"]["repository_id"] is not None):
        result.add("POLICY ERROR", "model-runtime-abstraction", "model-runtime", "logical model-runtime must remain provider-neutral")
    if model and "ollama" in model["purpose"].lower():
        result.add("POLICY ERROR", "model-runtime-provider-coupling", "model-runtime", "provider names belong in optional implementation metadata, not the platform abstraction")

    source_binding = repositories["source_binding"]
    if source_binding["credentials_in_manifest"] is not False or source_binding["correctness_anchor"] != "VERIFIED_FULL_COMMIT":
        result.add("POLICY ERROR", "repository-correctness-anchor", "manifests/repositories.json", "repository correctness must use credential-free verified full commits")
    repository_ids = [item["id"] for item in repositories["repositories"]]
    for duplicate in _duplicates(repository_ids):
        result.add("SEMANTIC ERROR", "duplicate-repository", "manifests/repositories.json", f"duplicate repository identity {duplicate!r}")

    gate_ids = [item["id"] for item in gates]
    for duplicate in _duplicates(gate_ids):
        result.add("SEMANTIC ERROR", "duplicate-readiness-gate", "manifests/readiness-gates.json", f"duplicate readiness gate {duplicate!r}")

    if compatibility["conflict_policy"] != "FAIL_CLOSED" or compatibility["implicit_fallback"] is not False:
        result.add("POLICY ERROR", "compatibility-fail-closed", "manifests/compatibility.json", "compatibility must be explicit and fail closed")
    canonical_names = {"Kalvin", "Kal", "Beepy"}
    historical_names = {"GoodWill", "Odysseus", "MBC Intelligence"}
    compatibility_ids = [entry["id"] for entry in compatibility["entries"]]
    for duplicate in _duplicates(compatibility_ids):
        result.add("SEMANTIC ERROR", "duplicate-compatibility", "manifests/compatibility.json", f"duplicate compatibility identity {duplicate!r}")
    for entry in compatibility["entries"]:
        if entry["legacy_identifier"] not in historical_names:
            result.add("POLICY ERROR", "compatibility-legacy-name", entry["id"], "legacy identifier must be an explicit historical canonical name")
        if entry["canonical_replacement"] not in canonical_names:
            result.add("POLICY ERROR", "compatibility-canonical-name", entry["id"], "canonical replacement must be Kalvin, Kal, or Beepy")

    for catalog_name, document in architecture.catalogs.items():
        for location, value in _walk_strings(document):
            reason = sensitive_value_reason(value)
            if reason:
                result.add("POLICY ERROR", "secret-looking-value", f"manifests/{catalog_name}.json:{location}", f"{reason} is forbidden in declarative contracts")
            if legacy_runtime_path(value):
                result.add("POLICY ERROR", "legacy-runtime-path", f"manifests/{catalog_name}.json:{location}", "legacy absolute runtime path is forbidden")
    for profile_name, document in architecture.profiles.items():
        for location, value in _walk_strings(document):
            reason = sensitive_value_reason(value)
            if reason:
                result.add("POLICY ERROR", "secret-looking-value", f"deploy/profiles/{profile_name}.json:{location}", f"{reason} is forbidden in declarative contracts")


def validate_bundle(architecture: Architecture) -> ValidationResult:
    """Validate a loaded architecture without reading host or runtime state."""
    result = ValidationResult()
    validate_schemas(architecture, result)
    if result.findings:
        return result
    _validate_vocabularies(architecture, result)
    _validate_components(architecture, result)
    _validate_profiles(architecture, result)
    _validate_policy(architecture, result)
    return result


def validate_architecture(root: Path | None = None) -> tuple[Architecture | None, ValidationResult]:
    architecture, load_findings = load_architecture(root)
    if architecture is None:
        return None, ValidationResult(load_findings)
    return architecture, validate_bundle(architecture)
