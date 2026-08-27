# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command-line contract for validation and resolution only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .models import UserInputError
from .output import plan_text, stable_json, validation_json, validation_text
from .resolver import resolve_plan
from .validation import validate_architecture


EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 2
EXIT_INTERNAL_FAILURE = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m kalvin",
        description="Validate Kalvin declarations and calculate secret-free resolved plans without changing a host.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate declarative architecture contracts")
    validate.add_argument("--format", choices=("text", "json"), default="text", help="validation presentation (default: text)")
    resolve = subparsers.add_parser("resolve", help="calculate a deterministic resolved plan; never deploy")
    resolve.add_argument("--profile", required=True, help="profile ID: lab, core, or storage")
    resolve.add_argument("--lock", required=True, type=Path, help="secret-free immutable repository/version lock JSON")
    resolve.add_argument("--enable", action="append", default=[], metavar="COMPONENT", help="explicitly select a default-off optional component (repeatable)")
    resolve.add_argument("--format", choices=("text", "json"), default="text", help="resolved-plan presentation (default: text)")
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
        plan = resolve_plan(args.profile, args.lock, enabled_optional=args.enable)
        sys.stdout.write(stable_json(plan) if args.format == "json" else plan_text(plan))
        return EXIT_SUCCESS
    except UserInputError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return EXIT_VALIDATION_FAILURE
    except Exception as exc:  # unexpected failures intentionally map to a distinct documented exit
        sys.stderr.write(f"INTERNAL ERROR [{type(exc).__name__}]: {exc}\n")
        return EXIT_INTERNAL_FAILURE
