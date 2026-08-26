"""Validate Kalvin's non-operational Phase 4C architecture contracts.

This standard-library-only validator reads repository declarations. It never
performs deployment, contacts a service, resolves a secret, or mutates a host.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DECLARATION_DIRS = (ROOT / "deploy", ROOT / "manifests", ROOT / "schemas")
PROFILE_IDS = {"lab", "core", "storage"}
REPOSITORY_IDS = {"kalvin", "kal", "beepy"}

failures: list[str] = []
checks = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    """Record one named contract check."""
    global checks
    checks += 1
    if not condition:
        failures.append(f"{name}: {detail or 'failed'}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"JSON parse {path.relative_to(ROOT)}: {exc}")
        return None


def git_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return False


def validate_schema(value: Any, schema: dict[str, Any], location: str) -> list[str]:
    """Validate the JSON Schema subset used by Phase 4C artifacts."""
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not any(type_matches(value, item) for item in expected_types):
            return [f"{location}: expected {expected_types}, got {type(value).__name__}"]

    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: unknown value {value!r}")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{location}: string is shorter than minLength")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{location}: string does not match {schema['pattern']!r}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{location}: array is shorter than minItems")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, item_schema, f"{location}[{index}]"))

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{location}: missing required key {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{location}: unexpected key {key!r}")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_schema(value[key], child_schema, f"{location}.{key}"))
    return errors


json_paths = sorted(path for base in DECLARATION_DIRS for path in base.rglob("*.json"))
documents = {path: load_json(path) for path in json_paths}
check("all declarations parse as JSON", all(value is not None for value in documents.values()))

schema_paths = sorted((ROOT / "schemas").glob("*.json"))
schemas = {path.name: documents[path] for path in schema_paths}
schema_ids = [schema.get("$id") for schema in schemas.values() if isinstance(schema, dict)]
check("JSON Schema identifiers are unique", len(schema_ids) == len(set(schema_ids)), repr(schema_ids))
check(
    "JSON Schemas use Draft 2020-12",
    all(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema" for schema in schemas.values()),
)

schema_validation_errors: list[str] = []
architecture_docs: list[dict[str, Any]] = []
for path in sorted([*(ROOT / "deploy").rglob("*.json"), *(ROOT / "manifests").rglob("*.json")]):
    document = documents[path]
    if not isinstance(document, dict):
        continue
    architecture_docs.append(document)
    schema_ref = document.get("$schema", "")
    schema_path = (path.parent / schema_ref).resolve()
    if not schema_path.is_relative_to(ROOT) or schema_path not in documents:
        schema_validation_errors.append(f"{path.relative_to(ROOT)}: unresolved schema {schema_ref!r}")
        continue
    schema_validation_errors.extend(
        validate_schema(document, documents[schema_path], str(path.relative_to(ROOT)))
    )
check("declarations satisfy their local schemas", not schema_validation_errors, "; ".join(schema_validation_errors))
check(
    "all architecture declarations are explicitly non-operational",
    all(doc.get("contract_status") == "reference-architecture" and doc.get("operational") is False for doc in architecture_docs),
)

vocab = documents[ROOT / "manifests/vocabularies.json"]
component_doc = documents[ROOT / "manifests/components.json"]
gate_doc = documents[ROOT / "manifests/readiness-gates.json"]
repository_doc = documents[ROOT / "manifests/repositories.json"]
compatibility_doc = documents[ROOT / "manifests/compatibility.json"]
profiles = [documents[path] for path in sorted((ROOT / "deploy/profiles").glob("*.json"))]

components = component_doc["components"]
component_ids = [item["id"] for item in components]
component_by_id = {item["id"]: item for item in components}
gates = gate_doc["gates"]
gate_ids = [item["id"] for item in gates]
gate_id_set = set(gate_ids)
repositories = repository_doc["repositories"]
repository_ids = [item["id"] for item in repositories]
profile_ids = [item["id"] for item in profiles]

check("exact initial profile set", set(profile_ids) == PROFILE_IDS and len(profile_ids) == 3, repr(profile_ids))
check("profile identifiers are unique", len(profile_ids) == len(set(profile_ids)), repr(profile_ids))
check("component identifiers are unique", len(component_ids) == len(set(component_ids)), repr(component_ids))
check("readiness gate identifiers are unique", len(gate_ids) == len(set(gate_ids)), repr(gate_ids))
check("repository identifiers are unique and complete", set(repository_ids) == REPOSITORY_IDS and len(repository_ids) == 3, repr(repository_ids))

state_classes = {item["id"] for item in vocab["state_classes"]}
backup_classes = set(vocab["backup_classes"])
exposure_classes = set(vocab["exposure_classes"])
privilege_classes = set(vocab["privilege_classes"])
dependency_kinds = set(vocab["dependency_kinds"])
profile_requirements = set(vocab["profile_requirements"])
readiness_classes = set(vocab["readiness_classes"])
compatibility_statuses = set(vocab["compatibility_statuses"])

check("required state classes are exact", state_classes == {"AUTHORITATIVE", "DERIVED", "EPHEMERAL", "CONFIGURATION", "SECRET", "LOG"}, repr(state_classes))
check("backup classes are exact", backup_classes == {"REQUIRED", "REBUILDABLE", "EXCLUDED"}, repr(backup_classes))
check("exposure classes are exact", exposure_classes == {"PROCESS_LOCAL", "HOST_INTERNAL", "PLATFORM_INTERNAL", "LAN", "OVERLAY", "PUBLIC"}, repr(exposure_classes))
check("privilege classes are exact", privilege_classes == {"UNPRIVILEGED_APPLICATION", "LIMITED_PLATFORM_SERVICE", "HOST_ADMINISTRATIVE", "EXTERNAL_HOST_MANAGEMENT"}, repr(privilege_classes))
check("dependency kinds are exact", dependency_kinds == {"STARTUP", "HEALTH", "READINESS", "OPTIONAL_INTEGRATION"}, repr(dependency_kinds))
check("profile requirements are exact", profile_requirements == {"REQUIRED", "OPTIONAL", "FORBIDDEN"}, repr(profile_requirements))

component_errors: list[str] = []
for component in components:
    component_id = component["id"]
    if component["privilege_class"] not in privilege_classes:
        component_errors.append(f"{component_id}: unknown privilege")
    if component["health_readiness_class"] not in readiness_classes:
        component_errors.append(f"{component_id}: unknown readiness class")
    if component["health_gate"] not in gate_id_set or not set(component["readiness_gates"]) <= gate_id_set:
        component_errors.append(f"{component_id}: unknown health/readiness gate")
    if component["exposure"]["default"] not in component["exposure"]["allowed"]:
        component_errors.append(f"{component_id}: default exposure is not allowed")
    if not set(component["exposure"]["allowed"]) <= exposure_classes:
        component_errors.append(f"{component_id}: unknown exposure class")
    for dependency in component["dependencies"]:
        if dependency["component"] not in component_by_id or dependency["kind"] not in dependency_kinds:
            component_errors.append(f"{component_id}: invalid dependency")
    if component["version"]["source"] == "REPOSITORY_LOCK" and component["version"]["repository_id"] not in REPOSITORY_IDS:
        component_errors.append(f"{component_id}: invalid repository lock")
    for state_item in component["state_requirements"]:
        if state_item["class"] not in state_classes or state_item["backup"] not in backup_classes:
            component_errors.append(f"{component_id}: unknown state or backup class")
        expected_backup = {"AUTHORITATIVE": "REQUIRED", "DERIVED": "REBUILDABLE"}.get(state_item["class"], "EXCLUDED")
        if state_item["backup"] != expected_backup:
            component_errors.append(f"{component_id}.{state_item['id']}: unsafe state/backup pairing")
check("component references and state policy are valid", not component_errors, "; ".join(component_errors))

profile_errors: list[str] = []
for profile in profiles:
    profile_id = profile["id"]
    selections = profile["components"]
    selected_ids = [item["id"] for item in selections]
    if set(selected_ids) != set(component_ids) or len(selected_ids) != len(component_ids):
        profile_errors.append(f"{profile_id}: component catalog is not represented exactly once")
    if not set(profile["required_readiness_gates"]) <= gate_id_set:
        profile_errors.append(f"{profile_id}: unknown required readiness gate")
    if profile["default_exposure_ceiling"] not in exposure_classes:
        profile_errors.append(f"{profile_id}: unknown exposure ceiling")
    for selection in selections:
        component = component_by_id[selection["id"]]
        if selection["requirement"] not in profile_requirements:
            profile_errors.append(f"{profile_id}.{selection['id']}: unknown requirement")
        if selection["requirement"] != component["default_requirement_by_profile"][profile_id]:
            profile_errors.append(f"{profile_id}.{selection['id']}: profile/catalog mismatch")
        if selection["default_enabled"] != (selection["requirement"] == "REQUIRED"):
            profile_errors.append(f"{profile_id}.{selection['id']}: unsafe default")
        allowed = profile_id in component["allowed_profiles"]
        if allowed == (selection["requirement"] == "FORBIDDEN"):
            profile_errors.append(f"{profile_id}.{selection['id']}: allowed-profile mismatch")
    for exception in profile["exposure_exceptions"]:
        if exception["component"] not in component_by_id or exception["maximum"] not in exposure_classes:
            profile_errors.append(f"{profile_id}: invalid exposure exception")
        if not set(exception["requires_gates"]) <= gate_id_set:
            profile_errors.append(f"{profile_id}: unknown exposure-exception gate")
check("profiles match component catalog and vocabulary", not profile_errors, "; ".join(profile_errors))

profile_by_id = {item["id"]: item for item in profiles}
core = profile_by_id["core"]
storage = profile_by_id["storage"]
lab = profile_by_id["lab"]
core_selection = {item["id"]: item["requirement"] for item in core["components"]}
storage_selection = {item["id"]: item["requirement"] for item in storage["components"]}
check(
    "Core production and RAG interlocks",
    core["production_mode"]
    and core["repository_policy"] == "REVIEWED_REF_AND_IMMUTABLE_RESOLUTION_REQUIRED"
    and core_selection["backup-client"] == "REQUIRED"
    and core_selection["storage-backup-target"] == "FORBIDDEN"
    and "kal.rag-status-durable" in core["required_readiness_gates"],
)
check(
    "Storage excludes application compute and owns retention",
    all(storage_selection[item] == "FORBIDDEN" for item in ("kal", "beepy", "model-runtime"))
    and storage_selection["storage-backup-target"] == "REQUIRED"
    and storage["backup_posture"] == "RETENTION_AND_RESTORE_SOURCE_AUTHORITY",
)
check(
    "Lab compatibility and public exposure are default off",
    not lab["production_mode"]
    and all(not item["default_enabled"] for item in lab["components"] if item["requirement"] == "OPTIONAL")
    and len(lab["exposure_exceptions"]) == 1
    and lab["exposure_exceptions"][0]["component"] == "public-test-exposure",
)
check(
    "public exposure is isolated to the explicit lab component",
    all(
        "PUBLIC" not in component["exposure"]["allowed"] or component["id"] == "public-test-exposure"
        for component in components
    )
    and all(not profile["exposure_exceptions"] for profile in (core, storage)),
)
check(
    "accepted components avoid administrative privilege classes",
    all(component["privilege_class"] in {"UNPRIVILEGED_APPLICATION", "LIMITED_PLATFORM_SERVICE"} for component in components),
)
check(
    "Kal and Beepy ownership remains external",
    component_by_id["kal"]["owner"] == "KAL"
    and component_by_id["beepy"]["owner"] == "BEEPY"
    and component_by_id["kal"]["version"]["repository_id"] == "kal"
    and component_by_id["beepy"]["version"]["repository_id"] == "beepy",
)
check(
    "model runtime remains implementation-neutral",
    component_by_id["model-runtime"]["version"]["source"] == "IMPLEMENTATION_LOCK"
    and component_by_id["model-runtime"]["version"]["repository_id"] is None,
)
check(
    "repository declarations are independent and immutable",
    repository_doc["source_binding"]["credentials_in_manifest"] is False
    and repository_doc["source_binding"]["correctness_anchor"] == "VERIFIED_FULL_COMMIT"
    and all(not item["submodule"] and not item["vendored"] and item["resolved_full_commit_required"] for item in repositories),
)
check(
    "compatibility is explicit and fail-closed",
    compatibility_doc["conflict_policy"] == "FAIL_CLOSED"
    and compatibility_doc["implicit_fallback"] is False
    and all(
        set(entry) == {"id", "legacy_identifier", "canonical_replacement", "consumer", "reason", "owner", "test_contract", "retirement_gate"}
        for entry in compatibility_doc["entries"]
    ),
)

all_paths = git_paths()
tracked_relative = {path.relative_to(ROOT).as_posix() for path in all_paths}
check("no Git submodules", ".gitmodules" not in tracked_relative and not any(path.is_dir() for path in all_paths))
check(
    "no application source is vendored",
    not any(path.parts[0] in {"kal", "beepy", "apps", "vendor"} for path in (item.relative_to(ROOT) for item in all_paths)),
)
check("no LICENSE was invented", not any(path.name.upper().startswith("LICENSE") for path in all_paths))

ignored_examples = [
    ".env",
    ".env.production",
    "secrets/service/credential",
    "credentials/backup/token",
    "id_rsa",
    "operator.key",
    "deployment.local.json",
    "state.sqlite",
    "backups/authoritative.tar",
    "logs/service.log",
    "tests/__pycache__/validator.pyc",
]
visible_examples = [".env.example", "docs/example.json", "manifests/components.json", "tests/fixture.sql"]
ignore_errors: list[str] = []
for example in ignored_examples:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", example],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        ignore_errors.append(f"expected ignored: {example}")
for example in visible_examples:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", example],
        cwd=ROOT,
        check=False,
    )
    if result.returncode == 0:
        ignore_errors.append(f"expected visible: {example}")
check(".gitignore protects private/runtime artifacts without hiding safe examples", not ignore_errors, "; ".join(ignore_errors))

operational_patterns = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"#!\s*/(?:usr/)?bin/",
        r"\bdocker\s+(?:compose|run|exec)\b",
        r"\bsystemctl\b",
        r"\bsudo\b",
        r"\b(?:iptables|nft|ufw)\b",
        r"\b(?:apt-get|apt)\s+install\b",
        r"\btailscale\s+up\b",
        r"\brsync\b",
        r"\brm\s+-[a-z]*r",
    )
]
declaration_text = "\n".join(path.read_text(encoding="utf-8") for path in json_paths)
check(
    "profiles and manifests contain no operational shell procedures",
    not any(pattern.search(declaration_text) for pattern in operational_patterns),
)

text_paths = [path for path in all_paths if path.suffix.lower() in {".md", ".json", ".py", ".gitignore"} or path.name in {"README.md", "AGENTS.md", "CONTRIBUTING.md", ".gitignore"}]
publication_text = "\n".join(path.read_text(encoding="utf-8") for path in text_paths)
private_patterns = [
    re.compile(r"\b10(?:\.\d{1,3}){3}\b"),
    re.compile(r"\b192\.168(?:\.\d{1,3}){2}\b"),
    re.compile(r"\b172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}\b"),
    re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|github_pat|xox[baprs])-[_A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bssh\s+[A-Za-z0-9._-]+@[^\s]+", re.IGNORECASE),
    re.compile(r"/[A-Za-z0-9._/-]*(?:odysseus-ai|mbc-intelligence|goodwill-portable)(?:/|\b)", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
]
publication_hits = [pattern.pattern for pattern in private_patterns if pattern.search(publication_text)]
check("publication safety patterns are absent", not publication_hits, repr(publication_hits))

link_errors: list[str] = []
link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
for path in (item for item in all_paths if item.suffix.lower() == ".md"):
    for target in link_pattern.findall(path.read_text(encoding="utf-8")):
        clean_target = target.strip().split("#", 1)[0]
        if not clean_target or re.match(r"^[a-z][a-z0-9+.-]*:", clean_target, re.IGNORECASE):
            continue
        resolved = (path.parent / clean_target).resolve()
        if not resolved.is_relative_to(ROOT) or not resolved.exists():
            link_errors.append(f"{path.relative_to(ROOT)} -> {target}")
check("internal Markdown links resolve", not link_errors, "; ".join(link_errors))

mode_errors: list[str] = []
for path in all_paths:
    file_stat = path.lstat()
    if stat.S_ISLNK(file_stat.st_mode):
        mode_errors.append(f"symlink: {path.relative_to(ROOT)}")
    if file_stat.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        mode_errors.append(f"executable: {path.relative_to(ROOT)}")
check("no symlinks or unexpected executable files", not mode_errors, "; ".join(mode_errors))
check(
    "all text contracts have final newlines",
    all(path.read_bytes().endswith(b"\n") for path in text_paths),
)

if failures:
    print(f"FAIL: {len(failures)} of {checks} architecture checks failed", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    raise SystemExit(1)

print(
    f"PASS: {checks} architecture checks; "
    f"{len(profiles)} profiles, {len(components)} components, "
    f"{len(gates)} readiness gates, {len(repositories)} repositories"
)
