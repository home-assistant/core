"""Common fixtures for the Tilt Pi tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from tiltpi import TiltColor, TiltHydrometerData

from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

TEST_NAME = "Test Tilt Pi"
TEST_HOST = "192.168.1.123"
TEST_PORT = 1880
TEST_URL = f"http://{TEST_HOST}:{TEST_PORT}"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tilt_pi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
        },
    )


@pytest.fixture
def mock_tiltpi_client() -> Generator[AsyncMock]:
    """Mock a TiltPi client."""
    with (
        patch(
            "homeassistant.components.tilt_pi.coordinator.TiltPiClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.tilt_pi.config_flow.TiltPiClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_hydrometers.return_value = [
            TiltHydrometerData(
                mac_id="00:1A:2B:3C:4D:5E",
                color=TiltColor.BLACK,
                temperature=55.0,
                gravity=1.010,
            ),
            TiltHydrometerData(
                mac_id="00:1s:99:f1:d2:4f",
                color=TiltColor.YELLOW,
                temperature=68.0,
                gravity=1.015,
            ),
        ]
        yield client
