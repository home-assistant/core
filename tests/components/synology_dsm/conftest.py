"""Configure Synology DSM tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.synology_dsm.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="mock_dsm")
def fixture_dsm():
    """Set up SynologyDSM API fixture."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.network.update = AsyncMock(return_value=True)
        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)

    return dsm
