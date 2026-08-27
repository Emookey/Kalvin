# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module entry point for ``python -m kalvin``."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
