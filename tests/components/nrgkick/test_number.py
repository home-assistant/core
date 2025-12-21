"""Tests for the NRGkick number platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.nrgkick.api import NRGkickApiClientError
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


async def test_number_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test number entities."""
    mock_config_entry.add_to_hass(hass)

    # Setup mock data
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    # Setup entry
    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Helper to get entity_id by unique ID
    entity_registry = er.async_get(hass)

    def get_entity_id_by_key(key):
        unique_id = f"TEST123456_{key}"
        return entity_registry.async_get_entity_id("number", "nrgkick", unique_id)

    # 1. Current Set
    entity_id = get_entity_id_by_key("current_set")
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert float(state.state) == 16.0
    assert state.attributes["min"] == 6.0
    assert state.attributes["max"] == 32.0  # From mock_info_data rated_current

    # Test set value
    mock_nrgkick_api.set_current.return_value = {"current_set": 10.0}

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, "value": 10.0},
        blocking=True,
    )

    mock_nrgkick_api.set_current.assert_called_once_with(10.0)

    # Verify state update (coordinator should update)
    state = hass.states.get(entity_id)
    assert state
    assert float(state.state) == 10.0

    # 2. Energy Limit
    entity_id = get_entity_id_by_key("energy_limit")
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert float(state.state) == 0.0

    # Test set value
    mock_nrgkick_api.set_energy_limit.return_value = {"energy_limit": 5000}

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, "value": 5000},
        blocking=True,
    )

    mock_nrgkick_api.set_energy_limit.assert_called_once_with(5000)
    state = hass.states.get(entity_id)
    assert state
    assert float(state.state) == 5000.0

    # 3. Phase Count
    entity_id = get_entity_id_by_key("phase_count")
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert float(state.state) == 3.0

    # Test set value
    mock_nrgkick_api.set_phase_count.return_value = {"phase_count": 1}

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, "value": 1},
        blocking=True,
    )

    mock_nrgkick_api.set_phase_count.assert_called_once_with(1)
    state = hass.states.get(entity_id)
    assert state
    assert float(state.state) == 1.0


async def test_number_set_value_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test error handling when setting value."""
    mock_config_entry.add_to_hass(hass)

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Mock error
    mock_nrgkick_api.set_current.side_effect = NRGkickApiClientError("API Error")

    # Helper to get entity_id by unique ID
    entity_registry = er.async_get(hass)
    unique_id = "TEST123456_current_set"
    entity_id = entity_registry.async_get_entity_id("number", "nrgkick", unique_id)
    assert entity_id

    with pytest.raises(
        HomeAssistantError,
        match=r"Failed to set current_set to 10\.0\. API Error",
    ):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, "value": 10.0},
            blocking=True,
        )


async def test_number_device_error_message(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test that device error messages are surfaced to user."""
    mock_config_entry.add_to_hass(hass)

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Simulate API returning error with "Response" field
    # (e.g., "Phase count change is blocked by solar-charging")
    mock_nrgkick_api.set_phase_count.return_value = {
        "Response": "Phase count change is blocked by solar-charging"
    }

    entity_registry = er.async_get(hass)
    unique_id = "TEST123456_phase_count"
    entity_id = entity_registry.async_get_entity_id("number", "nrgkick", unique_id)
    assert entity_id

    # The error message from the device should be included in the exception
    with pytest.raises(
        HomeAssistantError,
        match=r"Phase count change is blocked by solar-charging",
    ):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, "value": 1},
            blocking=True,
        )
