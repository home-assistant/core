"""Tests for the Growatt server number platform."""

from growattServer import GrowattV1ApiError
import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


async def test_number_entities_created(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry,
) -> None:
    """Test that number entities are created for MIN devices."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Filter for number entities only
    number_entities = [
        entity
        for entity in entities
        if entity.platform == "growatt_server" and entity.domain == "number"
    ]

    # We should have 4 number entities for MIN devices
    assert len(number_entities) == 4

    # Verify unique IDs
    number_unique_ids = [entity.unique_id for entity in number_entities]
    number_unique_ids.sort()

    expected_unique_ids = [
        "MIN123456_charge_power_rate",
        "MIN123456_charge_stop_soc",
        "MIN123456_discharge_power_rate",
        "MIN123456_discharge_stop_soc",
    ]
    expected_unique_ids.sort()

    assert number_unique_ids == expected_unique_ids

    # Verify entity IDs
    expected_entities = [
        "number.min123456_charge_power_rate",
        "number.min123456_charge_stop_soc",
        "number.min123456_discharge_power_rate",
        "number.min123456_discharge_stop_soc",
    ]

    entity_ids = [e.entity_id for e in number_entities]
    for expected_id in expected_entities:
        assert expected_id in entity_ids


async def test_number_entity_values(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry,
) -> None:
    """Test that number entities have correct values."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check entity values
    charge_power_state = hass.states.get("number.min123456_charge_power_rate")
    assert charge_power_state is not None
    assert float(charge_power_state.state) == 50.0

    charge_soc_state = hass.states.get("number.min123456_charge_stop_soc")
    assert charge_soc_state is not None
    assert float(charge_soc_state.state) == 10.0

    discharge_power_state = hass.states.get("number.min123456_discharge_power_rate")
    assert discharge_power_state is not None
    assert float(discharge_power_state.state) == 80.0

    discharge_soc_state = hass.states.get("number.min123456_discharge_stop_soc")
    assert discharge_soc_state is not None
    assert float(discharge_soc_state.state) == 20.0


async def test_set_number_value_success(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry,
) -> None:
    """Test setting a number entity value successfully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            "entity_id": "number.min123456_charge_power_rate",
            ATTR_VALUE: 75,
        },
        blocking=True,
    )

    # Verify API was called with correct parameters
    mock_growatt_api.min_write_parameter.assert_called_once_with(
        "MIN123456", "charge_power", 75
    )


async def test_set_number_value_api_error(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry,
) -> None:
    """Test handling API error when setting number value."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock API to raise error
    mock_growatt_api.min_write_parameter.side_effect = GrowattV1ApiError("API Error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                "entity_id": "number.min123456_charge_power_rate",
                ATTR_VALUE: 75,
            },
            blocking=True,
        )
