"""Util to handle processes."""

from __future__ import annotations

import subprocess
from typing import Any

# mypy: disallow-any-generics


def kill_subprocess(
    # pylint: disable=unsubscriptable-object # https://github.com/PyCQA/pylint/issues/4369
    process: subprocess.Popen[Any],
) -> None:
    """Force kill a subprocess and wait for it to exit."""
    process.kill()
    process.communicate()
    process.wait()

    del process
