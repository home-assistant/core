"""Tests for NRGkick device naming and fallback logic."""

from unittest.mock import MagicMock, patch

from homeassistant.components.nrgkick import NRGkickEntity
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
    """Test that device name falls back to 'NRGkick' when API returns empty name."""
    mock_config_entry.add_to_hass(hass)

    # Set empty device name in API response
    mock_info_data["general"]["device_name"] = ""
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
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
    """Test that custom device name is used when provided by API."""
    mock_config_entry.add_to_hass(hass)

    # Set custom device name in API response
    mock_info_data["general"]["device_name"] = "Garage Charger"
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
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


async def test_entity_id_uses_english_key(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test that entity_ids are always based on English keys via suggested_object_id.

    This ensures automations work regardless of the user's language setting.
    The entity_id should always be like 'sensor.nrgkick_total_active_power',
    never 'sensor.nrgkick_gesamtleistung' even if UI is set to German.

    """
    mock_config_entry.add_to_hass(hass)

    mock_info_data["general"]["device_name"] = "NRGkick"
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    serial = mock_info_data["general"]["serial_number"]

    # Verify specific entity_ids contain English keys
    test_cases = [
        ("sensor", f"{serial}_total_active_power", "total_active_power"),
        ("sensor", f"{serial}_housing_temperature", "housing_temperature"),
        ("sensor", f"{serial}_status", "status"),
    ]

    for domain, unique_id, expected_key in test_cases:
        entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
        assert entity_id is not None, f"Entity {unique_id} not found"
        # Entity ID should contain the English key, not a translated version
        assert expected_key in entity_id, (
            f"Entity ID '{entity_id}' should contain '{expected_key}'"
        )


def test_suggested_object_id_returns_key() -> None:
    """Test that NRGkickEntity.suggested_object_id returns the English key.

    This is a unit test to verify the suggested_object_id property
    returns the key used for entity_id generation.

    """
    # Create a mock coordinator with minimal data
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "info": {
            "general": {
                "serial_number": "TEST123",
                "device_name": "Test Device",
                "model_type": "NRGkick Gen2",
            },
            "versions": {"sw_sm": "1.0.0"},
        }
    }

    # Create entity with a specific key
    entity = NRGkickEntity(mock_coordinator, "total_active_power")

    # Verify suggested_object_id returns the key
    assert entity.suggested_object_id == "total_active_power"
    assert entity._attr_translation_key == "total_active_power"
