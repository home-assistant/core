"""Util to handle processes."""

from __future__ import annotations

import subprocess
from typing import Any


def kill_subprocess(process: subprocess.Popen[Any]) -> None:
    """Force kill a subprocess and wait for it to exit."""
    process.kill()
    process.communicate()
    process.wait()

    del process
