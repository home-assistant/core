"""Configure Synology DSM tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from awesomeversion import AwesomeVersion

from .consts import SERIAL


def mock_dsm_information(
    serial: str | None = SERIAL,
    update_result: bool = True,
    awesome_version: str = "7.2.2",
    model: str = "DS1821+",
    version_string: str = "DSM 7.2.2-72806 Update 3",
    ram: int = 32768,
    temperature: int = 58,
    uptime: int = 123456,
) -> Mock:
    """Mock SynologyDSM information."""
    return Mock(
        serial=serial,
        update=AsyncMock(return_value=update_result),
        awesome_version=AwesomeVersion(awesome_version),
        model=model,
        version_string=version_string,
        ram=ram,
        temperature=temperature,
        uptime=uptime,
    )
