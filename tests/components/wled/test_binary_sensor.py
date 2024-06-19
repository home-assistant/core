"""Tests for the WLED binary sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_available(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the firmware update binary sensor."""
    assert (state := hass.states.get("binary_sensor.wled_rgb_light_firmware"))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_no_update_available(hass: HomeAssistant) -> None:
    """Test the update binary sensor. There is no update available."""
    assert (state := hass.states.get("binary_sensor.wled_websocket_firmware"))
    assert state.state == STATE_OFF


async def test_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the binary update sensor is disabled by default."""
    assert not hass.states.get("binary_sensor.wled_rgb_light_firmware")

    assert (entry := entity_registry.async_get("binary_sensor.wled_rgb_light_firmware"))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
