"""Tests for NRGkick device naming and fallback logic."""

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_device_name_fallback(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test that device name is taken from the entry title."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, title="NRGkick")

    # Set empty device name in API response
    mock_info_data["general"]["device_name"] = ""
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify device registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_info_data["general"]["serial_number"])}
    )
    assert device
    assert device.name == "NRGkick"

    # Verify entity ID generation (should use default name)
    # With has_entity_name=True, if device name is "NRGkick",
    # entity ID should be sensor.nrgkick_total_active_power
    entity_registry = er.async_get(hass)
    unique_id = f"{mock_info_data['general']['serial_number']}_total_active_power"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.translation_key == "total_active_power"


async def test_device_name_custom(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test that custom device name is taken from the entry title."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, title="Garage Charger")

    # Set custom device name in API response
    mock_info_data["general"]["device_name"] = "Garage Charger"
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify device registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_info_data["general"]["serial_number"])}
    )
    assert device
    assert device.name == "Garage Charger"

    # Verify entity ID generation
    # With has_entity_name=True, if device name is "Garage Charger",
    # entity ID should be sensor.garage_charger_total_active_power
    entity_registry = er.async_get(hass)
    unique_id = f"{mock_info_data['general']['serial_number']}_total_active_power"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.translation_key == "total_active_power"
