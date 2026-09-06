"""Tests for the Mikrotik binary sensor platform."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_mikrotik_entry
from .const import BRIDGE1_INTERFACE, INTERFACE_DATA

from tests.common import snapshot_platform


async def test_binary_sensor_entities_created(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Mikrotik binary sensor entities are created with expected values."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.BINARY_SENSOR]):
        config_entry = await setup_mikrotik_entry(hass, interface_data=INTERFACE_DATA)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_binary_sensor_no_matching_interfaces(hass: HomeAssistant) -> None:
    """Test no binary sensor entities are created for interfaces without running key."""
    interface_without_running = {
        key: value for key, value in BRIDGE1_INTERFACE.items() if key != "running"
    }
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_mikrotik_entry(hass, interface_data=[interface_without_running])

    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == []


async def test_binary_sensor_skips_loopback_interfaces(hass: HomeAssistant) -> None:
    """Test no binary sensor entities are created for loopback interfaces."""
    loopback_interface = {**BRIDGE1_INTERFACE, "name": "lo", "type": "loopback"}
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_mikrotik_entry(hass, interface_data=[loopback_interface])

    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == []
