"""godice testing fixtures."""

from unittest.mock import AsyncMock

import godice
import pytest

from homeassistant.components.godice.const import CONF_SHELL, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from . import GODICE_DEVICE_SERVICE_INFO

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


@pytest.fixture
def fake_dice():
    """Mock a real GoDice."""
    return AsyncMock(godice.Dice)


@pytest.fixture
def config_entry(hass: HomeAssistant):
    """Mock a config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GODICE_DEVICE_SERVICE_INFO.address,
        data={
            CONF_NAME: GODICE_DEVICE_SERVICE_INFO.name,
            CONF_ADDRESS: GODICE_DEVICE_SERVICE_INFO.address,
            CONF_SHELL: godice.Shell.D6.name,
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry
