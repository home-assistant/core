"""Tests for the Homevolt entity."""

from __future__ import annotations

from unittest.mock import MagicMock

from homevolt import DeviceMetadata

from homeassistant.components.homevolt.const import DOMAIN, MANUFACTURER
from homeassistant.components.homevolt.switch import HomevoltLocalModeSwitch
from homeassistant.core import HomeAssistant

from .conftest import DEVICE_IDENTIFIER


async def test_homevolt_entity_device_info_with_metadata(
    hass: HomeAssistant,
) -> None:
    """Test HomevoltEntity device info when device_metadata is present."""
    coordinator = MagicMock()
    coordinator.data.unique_id = "40580137858664"
    coordinator.data.device_metadata = {
        DEVICE_IDENTIFIER: DeviceMetadata(name="Homevolt EMS", model="EMS-1000"),
    }
    coordinator.client.base_url = "http://127.0.0.1"

    entity = HomevoltLocalModeSwitch(coordinator)
    assert entity.device_info is not None
    assert entity.device_info["identifiers"] == {
        (DOMAIN, f"40580137858664_{DEVICE_IDENTIFIER}")
    }
    assert entity.device_info["configuration_url"] == "http://127.0.0.1"
    assert entity.device_info["manufacturer"] == MANUFACTURER
    assert entity.device_info["model"] == "EMS-1000"
    assert entity.device_info["name"] == "Homevolt EMS"


async def test_homevolt_entity_device_info_without_metadata(
    hass: HomeAssistant,
) -> None:
    """Test HomevoltEntity device info when device_metadata has no entry for device."""
    coordinator = MagicMock()
    coordinator.data.unique_id = "40580137858664"
    coordinator.data.device_metadata = {}
    coordinator.client.base_url = "http://127.0.0.1"

    entity = HomevoltLocalModeSwitch(coordinator)
    assert entity.device_info is not None
    assert entity.device_info["identifiers"] == {
        (DOMAIN, f"40580137858664_{DEVICE_IDENTIFIER}")
    }
    assert entity.device_info["manufacturer"] == MANUFACTURER
    assert entity.device_info["model"] is None
    assert entity.device_info["name"] is None
