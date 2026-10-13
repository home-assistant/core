"""Test the LIFX binary sensor platform."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import SERIAL, async_setup_lifx_entry, async_trigger_update
from .helpers import create_mock_hev_light


async def test_hev_cycle_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test HEV cycle state follows typed HEV state."""
    device = create_mock_hev_light()
    await async_setup_lifx_entry(hass, device)

    entity_id = "binary_sensor.my_group_my_bulb_clean_cycle"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.RUNNING

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry
    assert registry_entry.unique_id == f"{SERIAL}_hev_cycle_state"
    assert registry_entry.entity_category == EntityCategory.DIAGNOSTIC

    device.state.hev_cycle.remaining_s = 0
    await async_trigger_update(hass)

    assert hass.states.get(entity_id).state == STATE_OFF
