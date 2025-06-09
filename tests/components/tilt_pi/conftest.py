"""Common fixtures for the Tilt Pi tests."""

from unittest.mock import MagicMock

import pytest
from tiltpi import TiltPiClient

from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

TEST_NAME = "Test Tilt Pi"
TEST_HOST = "192.168.1.123"
TEST_PORT = 1880
TEST_URL = f"http://{TEST_HOST}:{TEST_PORT}"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
        },
        unique_id="test123",
    )


@pytest.fixture
def mock_tiltpi_client() -> MagicMock:
    """Mock TiltPi client."""
    return MagicMock(spec=TiltPiClient)
