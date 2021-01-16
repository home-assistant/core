"""Util to handle processes."""

import subprocess
from typing import Any

# mypy: disallow-any-generics


def kill_subprocess(process: subprocess.Popen[Any]) -> None:
    """Force kill a subprocess and wait for it to exit."""
    process.kill()
    process.communicate()
    process.wait()

    del process
