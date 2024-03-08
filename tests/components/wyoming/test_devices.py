"""Test Wyoming devices."""

from __future__ import annotations

from homeassistant.components.assist_pipeline.select import OPTION_PREFERRED
from homeassistant.components.wyoming import DOMAIN
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


async def test_device_registry_info(
    hass: HomeAssistant,
    satellite_device: SatelliteDevice,
    satellite_config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test info in device registry."""

    # Satellite uses config entry id since only one satellite per entry is
    # supported.
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, satellite_config_entry.entry_id)}
    )
    assert device is not None
    assert device.name == "Test Satellite"
    assert device.suggested_area == "Office"

    # Check associated entities
    assist_in_progress_id = satellite_device.get_assist_in_progress_entity_id(hass)
    assert assist_in_progress_id
    assist_in_progress_state = hass.states.get(assist_in_progress_id)
    assert assist_in_progress_state is not None
    assert assist_in_progress_state.state == STATE_OFF

    muted_id = satellite_device.get_muted_entity_id(hass)
    assert muted_id
    muted_state = hass.states.get(muted_id)
    assert muted_state is not None
    assert muted_state.state == STATE_OFF

    pipeline_entity_id = satellite_device.get_pipeline_entity_id(hass)
    assert pipeline_entity_id
    pipeline_state = hass.states.get(pipeline_entity_id)
    assert pipeline_state is not None
    assert pipeline_state.state == OPTION_PREFERRED


async def test_remove_device_registry_entry(
    hass: HomeAssistant,
    satellite_device: SatelliteDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a device registry entry."""

    # Check associated entities
    assist_in_progress_id = satellite_device.get_assist_in_progress_entity_id(hass)
    assert assist_in_progress_id
    assert hass.states.get(assist_in_progress_id) is not None

    muted_id = satellite_device.get_muted_entity_id(hass)
    assert muted_id
    assert hass.states.get(muted_id) is not None

    pipeline_entity_id = satellite_device.get_pipeline_entity_id(hass)
    assert pipeline_entity_id
    assert hass.states.get(pipeline_entity_id) is not None

    # Remove
    device_registry.async_remove_device(satellite_device.device_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Everything should be gone
    assert hass.states.get(assist_in_progress_id) is None
    assert hass.states.get(muted_id) is None
    assert hass.states.get(pipeline_entity_id) is None
