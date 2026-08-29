# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command-line contract for validation, read-only observation, and planning."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .drift import evaluate_host_drift, requirements_for_profile
from .host_inspector import HostInspector
from .models import UserInputError
from .output import drift_text, observed_host_text, plan_text, preflight_text, remediation_plan_text, requirements_text, stable_json, validation_json, validation_text
from .preflight import compare_preflight
from .remediation import generate_remediation_plan
from .resolver import resolve_plan
from .validation import validate_architecture


EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 2
EXIT_INTERNAL_FAILURE = 3
EXIT_BLOCKING_HOST_DRIFT = 4
EXIT_UNKNOWN_HOST_COMPLIANCE = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m kalvin",
        description="Validate, resolve, observe, compare, and plan without changing a host.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate declarative architecture contracts")
    validate.add_argument("--format", choices=("text", "json"), default="text", help="validation presentation (default: text)")
    resolve = subparsers.add_parser("resolve", help="calculate a deterministic resolved plan; never deploy")
    resolve.add_argument("--profile", required=True, help="profile ID: lab, core, or storage")
    resolve.add_argument("--lock", required=True, type=Path, help="secret-free immutable repository/version lock JSON")
    resolve.add_argument("--enable", action="append", default=[], metavar="COMPONENT", help="explicitly select a default-off optional component (repeatable)")
    resolve.add_argument("--format", choices=("text", "json"), default="text", help="resolved-plan presentation (default: text)")
    host = subparsers.add_parser("host", help="read-only local host observation and preflight")
    host_commands = host.add_subparsers(dest="host_command", required=True)
    inspect = host_commands.add_parser("inspect", help="emit a sanitized local observed-host snapshot")
    inspect.add_argument("--format", choices=("text", "json"), default="text", help="observed-host presentation (default: text)")
    requirements = host_commands.add_parser("requirements", help="display evidence-backed profile host requirements; observe nothing")
    requirements.add_argument("--profile", required=True, help="profile ID: lab, core, or storage")
    requirements.add_argument("--format", choices=("text", "json"), default="text", help="requirement-policy presentation (default: text)")
    preflight = host_commands.add_parser("preflight", help="compare resolved requirements with sanitized local observation")
    preflight.add_argument("--profile", required=True, help="profile ID: lab, core, or storage")
    preflight.add_argument("--lock", required=True, type=Path, help="secret-free immutable repository/version lock JSON")
    preflight.add_argument("--enable", action="append", default=[], metavar="COMPONENT", help="explicitly select a default-off optional component (repeatable)")
    preflight.add_argument("--format", choices=("text", "json"), default="text", help="preflight presentation (default: text)")
    drift = host_commands.add_parser("drift", help="report guidance-only host drift; never remediate")
    drift.add_argument("--profile", required=True, help="profile ID: lab, core, or storage")
    drift.add_argument("--lock", required=True, type=Path, help="secret-free immutable repository/version lock JSON")
    drift.add_argument("--enable", action="append", default=[], metavar="COMPONENT", help="explicitly select a default-off optional component (repeatable)")
    drift.add_argument("--format", choices=("text", "json"), default="text", help="drift-report presentation (default: text)")
    remediation_plan = host_commands.add_parser(
        "plan", help="produce a deterministic remediation plan; execution is unavailable"
    )
    remediation_plan.add_argument("--profile", required=True, help="profile ID: lab, core, or storage")
    remediation_plan.add_argument("--lock", required=True, type=Path, help="secret-free immutable repository/version lock JSON")
    remediation_plan.add_argument("--enable", action="append", default=[], metavar="COMPONENT", help="explicitly select a default-off optional component (repeatable)")
    remediation_plan.add_argument("--format", choices=("text", "json"), default="text", help="remediation-plan presentation (default: text)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            _, result = validate_architecture()
            rendered = validation_json(result) if args.format == "json" else validation_text(result)
            stream = sys.stdout if result.valid else sys.stderr
            stream.write(rendered)
            return EXIT_SUCCESS if result.valid else EXIT_VALIDATION_FAILURE
        if args.command == "resolve":
            plan = resolve_plan(args.profile, args.lock, enabled_optional=args.enable)
            sys.stdout.write(stable_json(plan) if args.format == "json" else plan_text(plan))
            return EXIT_SUCCESS
        if args.host_command == "requirements":
            architecture, validation = validate_architecture()
            if architecture is None or not validation.valid:
                raise UserInputError("Host requirement policy is invalid")
            document = requirements_for_profile(architecture.catalogs["host-requirements"], args.profile)
            sys.stdout.write(stable_json(document) if args.format == "json" else requirements_text(document))
            return EXIT_SUCCESS
        if args.host_command == "inspect":
            observed = HostInspector().inspect()
            sys.stdout.write(stable_json(observed) if args.format == "json" else observed_host_text(observed))
            return EXIT_SUCCESS
        plan = resolve_plan(args.profile, args.lock, enabled_optional=args.enable)
        architecture, validation = validate_architecture()
        if architecture is None or not validation.valid:
            raise UserInputError("Architecture became invalid before host comparison")
        observed = HostInspector().inspect()
        if args.host_command == "plan":
            drift_report = evaluate_host_drift(
                plan, observed, architecture.catalogs["host-requirements"]
            )
            result = generate_remediation_plan(
                plan,
                drift_report,
                architecture.catalogs["host-requirements"],
                architecture.catalogs["remediation-actions"],
                plan_schema=architecture.schemas["remediation-plan.schema.json"],
            )
            sys.stdout.write(stable_json(result) if args.format == "json" else remediation_plan_text(result))
            return EXIT_SUCCESS
        if args.host_command == "drift":
            result = evaluate_host_drift(plan, observed, architecture.catalogs["host-requirements"])
            sys.stdout.write(stable_json(result) if args.format == "json" else drift_text(result))
            if result["host_compliance"] == "UNSATISFIED":
                return EXIT_BLOCKING_HOST_DRIFT
            if result["host_compliance"] == "UNKNOWN":
                return EXIT_UNKNOWN_HOST_COMPLIANCE
            return EXIT_SUCCESS
        result = compare_preflight(plan, observed, architecture.catalogs["host-requirements"])
        sys.stdout.write(stable_json(result) if args.format == "json" else preflight_text(result))
        return EXIT_SUCCESS
    except UserInputError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return EXIT_VALIDATION_FAILURE
    except Exception as exc:  # unexpected failures intentionally map to a distinct documented exit
        sys.stderr.write(f"INTERNAL ERROR [{type(exc).__name__}]: {exc}\n")
        return EXIT_INTERNAL_FAILURE
