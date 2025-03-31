"""Define fixtures available for all tests."""

import pytest

from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SENSOR_TYPE

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_entry_factory():
    """Fixture to create a MockConfigEntry with a customizable sensor type."""
    return lambda sensor_type="curtain": MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: sensor_type,
        },
        unique_id="aabbccddeeff",
    )
