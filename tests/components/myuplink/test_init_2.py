"""Tests for init module - alternate fixtures."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.myuplink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def load_systems_file() -> str:
    """Load fixture file for systems."""
    return load_fixture("systems-2dev.json", DOMAIN)


@pytest.fixture
def load_device_file() -> str:
    """Fixture for loading device file."""
    return load_fixture("device-2dev.json", DOMAIN)


async def test_devices_multiple_created_count(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that multiple device are created."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)

    assert len(device_registry.devices) == 2
