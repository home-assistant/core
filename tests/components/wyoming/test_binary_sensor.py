"""Test Wyoming binary sensor devices."""

import pytest

from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import reload_satellite


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_assist_in_progress(
    hass: HomeAssistant,
    satellite_config_entry: ConfigEntry,
    satellite_device: SatelliteDevice,
) -> None:
    """Test assist in progress."""
    assist_in_progress_id = satellite_device.get_assist_in_progress_entity_id(hass)
    assert assist_in_progress_id

    state = hass.states.get(assist_in_progress_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert not satellite_device.is_active

    satellite_device.set_is_active(True)

    state = hass.states.get(assist_in_progress_id)
    assert state is not None
    assert state.state == STATE_ON
    assert satellite_device.is_active

    # test restore does *not* happen
    satellite_device = await reload_satellite(hass, satellite_config_entry.entry_id)

    state = hass.states.get(assist_in_progress_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert not satellite_device.is_active


async def test_assist_in_progress_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    satellite_device: SatelliteDevice,
) -> None:
    """Test assist in progress binary sensor is added disabled."""
    assist_in_progress_id = satellite_device.get_assist_in_progress_entity_id(hass)
    assert assist_in_progress_id

    assert not hass.states.get(assist_in_progress_id)
    entity_entry = entity_registry.async_get(assist_in_progress_id)
    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
