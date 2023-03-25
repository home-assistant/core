"""Test process util."""

import os
import subprocess

import pytest

from homeassistant.util import process


async def test_kill_process() -> None:
    """Test killing a process."""
    sleeper = subprocess.Popen(
        "sleep 1000",
        shell=True,  # nosec # shell by design
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid = sleeper.pid

    assert os.kill(pid, 0) is None

    process.kill_subprocess(sleeper)

    with pytest.raises(OSError):
        os.kill(pid, 0)
