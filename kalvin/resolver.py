# SPDX-License-Identifier: AGPL-3.0-or-later
"""Desired-profile to deterministic resolved-plan calculation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .graph import stable_topological_order
from .lockfile import LockData, load_lock
from .models import Architecture, UserInputError
from .validation import DECLARATIVE_VERIFIABLE_GATES, validate_architecture


DEVELOPMENT_REF = re.compile(r"(?:^|[/._-])development(?:$|[/._-])", re.IGNORECASE)


def _index(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def _selected_components(
    architecture: Architecture, profile: dict[str, Any], enabled_optional: Iterable[str]
) -> tuple[set[str], list[dict[str, str]]]:
    policy = _index(profile["components"])
    catalog_ids = set(_index(architecture.catalogs["components"]["components"]))
    requested = set(enabled_optional)
    unknown = sorted(requested - catalog_ids)
    if unknown:
        raise UserInputError(f"Unknown component(s): {', '.join(unknown)}. Available components: {', '.join(sorted(catalog_ids))}")
    for component_id in sorted(requested):
        requirement = policy[component_id]["requirement"]
        if requirement == "FORBIDDEN":
            raise UserInputError(f"Forbidden component {component_id!r}: profile {profile['id']!r} policy is FORBIDDEN")
    selected = {item["id"] for item in profile["components"] if item["requirement"] == "REQUIRED"}
    selected.update(requested)
    component_policy = []
    for item in sorted(profile["components"], key=lambda value: value["id"]):
        if item["id"] in selected:
            disposition = "SELECTED_REQUIRED" if item["requirement"] == "REQUIRED" else "SELECTED_OPTIONAL"
        elif item["requirement"] == "FORBIDDEN":
            disposition = "FORBIDDEN"
        else:
            disposition = "AVAILABLE_DEFAULT_OFF"
        component_policy.append({"id": item["id"], "disposition": disposition})
    return selected, component_policy


def _relationships(components: dict[str, dict[str, Any]], selected: set[str]) -> dict[str, list[dict[str, Any]]]:
    relationships = {"startup": [], "health": [], "readiness": [], "optional_integrations": []}
    names = {
        "STARTUP": "startup",
        "HEALTH": "health",
        "READINESS": "readiness",
        "OPTIONAL_INTEGRATION": "optional_integrations",
    }
    for consumer_id in sorted(selected):
        for dependency in sorted(
            components[consumer_id]["dependencies"], key=lambda item: (item["kind"], item["component"])
        ):
            dependency_id = dependency["component"]
            active = dependency_id in selected
            if dependency["required"] and not active:
                raise UserInputError(
                    f"Missing dependency: selected component {consumer_id!r} requires {dependency_id!r} via {dependency['kind']}; explicitly enable it when optional in this profile"
                )
            relationships[names[dependency["kind"]]].append(
                {
                    "component": consumer_id,
                    "dependency": dependency_id,
                    "required": dependency["required"],
                    "selected": active,
                    "partial_operation": dependency["partial_operation"],
                }
            )
    return relationships


def _required_locks(
    components: dict[str, dict[str, Any]], selected: set[str], lock: LockData, profile_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    repository_locks: list[dict[str, Any]] = []
    implementation_locks: list[dict[str, Any]] = []
    for component_id in sorted(selected):
        version = components[component_id]["version"]
        if version["source"] == "REPOSITORY_LOCK":
            repository_id = version["repository_id"]
            entry = lock.repository_entries.get(repository_id)
            if entry is None:
                raise UserInputError(f"Missing repository lock: component {component_id!r} requires repository {repository_id!r}")
            if profile_id == "core" and component_id in {"kal", "beepy"} and DEVELOPMENT_REF.search(entry["desired_ref"]):
                raise UserInputError(
                    f"Core repository policy rejects development application ref {entry['desired_ref']!r} for {component_id}; use a reviewed stable/release ref bound to a full commit"
                )
            repository_locks.append(
                {
                    "component": component_id,
                    "repository_id": repository_id,
                    "desired_ref": entry["desired_ref"],
                    "resolved_commit": entry["resolved_commit"],
                    "source_identity": entry.get("source_identity"),
                }
            )
        else:
            entry = lock.implementation_entries.get(component_id)
            if entry is None:
                raise UserInputError(f"Missing implementation lock: component {component_id!r} requires an exact implementation version")
            implementation_locks.append(
                {
                    "component": component_id,
                    "desired_ref": entry["desired_ref"],
                    "resolved_version": entry["resolved_version"],
                    "source_identity": entry.get("source_identity"),
                }
            )
    return repository_locks, implementation_locks


def resolve_plan(
    profile_id: str,
    lock_path: Path,
    *,
    enabled_optional: Iterable[str] = (),
    root: Path | None = None,
) -> dict[str, Any]:
    """Resolve declared intent in memory. No host observation or apply stage exists."""
    architecture, validation = validate_architecture(root)
    if architecture is None or not validation.valid:
        details = "; ".join(item.render() for item in validation.ordered())
        raise UserInputError(f"Architecture INVALID; resolution refused: {details}")
    profiles = {item["id"]: item for item in architecture.profiles.values()}
    if profile_id not in profiles:
        raise UserInputError(f"Unknown profile {profile_id!r}. Available profiles: {', '.join(sorted(profiles))}")
    profile = profiles[profile_id]
    component_by_id = _index(architecture.catalogs["components"]["components"])
    gate_by_id = _index(architecture.catalogs["readiness-gates"]["gates"])
    state_class_by_id = _index(architecture.catalogs["vocabularies"]["state_classes"])
    selected, component_policy = _selected_components(architecture, profile, enabled_optional)
    relationships = _relationships(component_by_id, selected)
    lock = load_lock(lock_path, architecture)
    repository_locks, implementation_locks = _required_locks(component_by_id, selected, lock, profile_id)

    startup_edges = [
        (item["dependency"], item["component"])
        for item in relationships["startup"]
        if item["selected"]
    ]
    dependency_order = stable_topological_order(selected, startup_edges)

    components: list[dict[str, Any]] = []
    configurations: list[dict[str, Any]] = []
    secret_references: list[dict[str, Any]] = []
    state: list[dict[str, Any]] = []
    exposures: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    compatibility_requirements: list[dict[str, Any]] = []
    profile_policy = _index(profile["components"])
    exposure_exceptions = {item["component"]: item for item in profile["exposure_exceptions"]}

    for component_id in dependency_order:
        component = component_by_id[component_id]
        requirement = profile_policy[component_id]["requirement"]
        components.append(
            {
                "id": component_id,
                "owner": component["owner"],
                "requirement": requirement,
                "purpose": component["purpose"],
                "version_source": component["version"]["source"],
            }
        )
        for item in component["configuration_requirements"]:
            configurations.append(
                {
                    "id": item["id"],
                    "component": component_id,
                    "owner": component["owner"],
                    "source_layer": item["source_layer"],
                    "required": item["required"],
                    "conflict_policy": item["conflict_policy"],
                }
            )
        for item in component["secret_references"]:
            secret_references.append(
                {
                    "id": item["id"],
                    "component": component_id,
                    "required": item["required"],
                    "resolution": "REFERENCE_ONLY",
                }
            )
        for item in component["state_requirements"]:
            state_class = state_class_by_id[item["class"]]
            state.append(
                {
                    "id": item["id"],
                    "component": component_id,
                    "owner": item["owner"],
                    "filesystem_destination": item["path"],
                    "state_class": item["class"],
                    "backup_policy": item["backup"],
                    "restore_semantics": state_class["restore_expectation"],
                    "rebuild_semantics": state_class["rebuild_behavior"],
                }
            )
        exposures.append(
            {
                "component": component_id,
                "declared_default": component["exposure"]["default"],
                "allowed": component["exposure"]["allowed"],
                "profile_ceiling": exposure_exceptions.get(component_id, {}).get("maximum", profile["default_exposure_ceiling"]),
                "explicit_exception": component_id in exposure_exceptions,
            }
        )
        identities.append(
            {
                "component": component_id,
                "identity_class": component["identity_class"],
                "privilege_class": component["privilege_class"],
            }
        )
        compatibility = component["compatibility"]
        if compatibility["status"] != "CANONICAL":
            compatibility_requirements.append(
                {
                    "component": component_id,
                    "status": compatibility["status"],
                    "retirement_gate": compatibility["retirement_gate"],
                }
            )

    readiness_gates: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    for gate_id in profile["required_readiness_gates"]:
        gate = gate_by_id[gate_id]
        declarative = gate_id in DECLARATIVE_VERIFIABLE_GATES
        readiness_gates.append(
            {
                "id": gate_id,
                "owner": gate["owner"],
                "class": gate["class"],
                "requirement": "REQUIRED",
                "verification_scope": "DECLARATIVE" if declarative else "EXTERNAL",
                "status": "VERIFIED" if declarative else "UNVERIFIED",
                "purpose": gate["purpose"],
            }
        )
        if not declarative:
            blockers.append({"type": "READINESS_GATE", "id": gate_id, "status": "REQUIRED_EXTERNAL_UNVERIFIED"})

    for item in configurations:
        if item["required"]:
            blockers.append({"type": "CONFIGURATION_VALUE", "id": item["id"], "status": "REQUIRED_EXTERNAL_UNVERIFIED"})
    for item in secret_references:
        if item["required"]:
            blockers.append({"type": "SECRET_REFERENCE", "id": item["id"], "status": "REQUIRED_EXTERNAL_UNVERIFIED"})

    production_readiness = "NOT_APPLICABLE" if not profile["production_mode"] else (
        "BLOCKED_EXTERNAL_GATE" if blockers else "READY"
    )
    return {
        "contract_version": "1.0.0",
        "kind": "KALVIN_RESOLVED_PLAN",
        "architecture_validity": "VALID",
        "resolution_status": "RESOLVED",
        "production_readiness": production_readiness,
        "selected_profile": profile_id,
        "profile_role": profile["role"],
        "production_mode": profile["production_mode"],
        "backup_posture": profile["backup_posture"],
        "component_policy": component_policy,
        "components": components,
        "repository_locks": repository_locks,
        "implementation_locks": implementation_locks,
        "dependency_order": dependency_order,
        "dependencies": relationships,
        "configuration_precedence": architecture.catalogs["vocabularies"]["configuration_source_layers"],
        "configuration_requirements": sorted(configurations, key=lambda item: (item["component"], item["id"])),
        "secret_references": sorted(secret_references, key=lambda item: (item["component"], item["id"])),
        "state_declarations": sorted(state, key=lambda item: (item["component"], item["id"])),
        "exposure": sorted(exposures, key=lambda item: item["component"]),
        "identity_and_privilege": sorted(identities, key=lambda item: item["component"]),
        "readiness_gates": readiness_gates,
        "compatibility_requirements": sorted(compatibility_requirements, key=lambda item: item["component"]),
        "unresolved_external_blockers": sorted(blockers, key=lambda item: (item["type"], item["id"])),
        "observed_or_deployed_state": "NOT_EVALUATED_BY_PHASE_4D",
    }
