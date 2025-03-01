"""Configure Synology DSM tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from awesomeversion import AwesomeVersion

from .consts import SERIAL


def mock_dsm_information(
    serial: str | None = SERIAL,
    update_result: bool = True,
    awesome_version: str = "7.2",
) -> Mock:
    """Mock SynologyDSM information."""
    return Mock(
        serial=serial,
        update=AsyncMock(return_value=update_result),
        awesome_version=AwesomeVersion(awesome_version),
    )
