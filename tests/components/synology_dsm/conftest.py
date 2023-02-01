"""Configure Synology DSM tests."""
from unittest.mock import AsyncMock, patch

import pytest


def pytest_configure(config):
    """Register custom marker for tests."""
    config.addinivalue_line(
        "markers", "no_bypass_setup: mark test to disable bypass_setup_fixture"
    )


@pytest.fixture(name="bypass_setup", autouse=True)
def bypass_setup_fixture(request):
    """Mock component setup."""
    if "no_bypass_setup" in request.keywords:
        yield
    else:
        with patch(
            "homeassistant.components.synology_dsm.async_setup_entry", return_value=True
        ):
            yield


@pytest.fixture(name="mock_dsm")
def fixture_dsm():
    """Set up SynologyDSM API fixture."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.network.update = AsyncMock(return_value=True)
        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)

    yield dsm
