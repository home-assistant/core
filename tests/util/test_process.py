"""Test process util."""

from functools import partial
import os
import subprocess

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util import process


async def test_kill_process(hass: HomeAssistant) -> None:
    """Test killing a process."""
    sleeper = await hass.async_add_executor_job(
        partial(  # noqa: S604 # shell by design
            subprocess.Popen,
            "sleep 1000",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    )
    pid = sleeper.pid

    assert os.kill(pid, 0) is None

    process.kill_subprocess(sleeper)

    with pytest.raises(OSError):
        os.kill(pid, 0)
