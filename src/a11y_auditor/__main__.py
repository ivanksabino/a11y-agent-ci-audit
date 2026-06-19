"""Permite executar o gate via `python -m a11y_auditor`."""

import sys

from a11y_auditor.gate import cli

sys.exit(cli())
