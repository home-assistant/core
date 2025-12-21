"""Tests for the NRGkick switch platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.nrgkick.api import NRGkickApiClientError
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_switch_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test switch entities."""
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

    # 1. Charge Pause
    # mock_control_data has "charge_pause": 0 -> False -> OFF
    state = hass.states.get("switch.nrgkick_test_charge_pause")
    assert state
    assert state.state == STATE_OFF

    # Test Turn On (Pause)
    mock_nrgkick_api.set_charge_pause.return_value = {"charge_pause": 1}

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.nrgkick_test_charge_pause"},
        blocking=True,
    )

    mock_nrgkick_api.set_charge_pause.assert_called_once_with(True)
    state = hass.states.get("switch.nrgkick_test_charge_pause")
    assert state
    assert state.state == STATE_ON

    # Test Turn Off (Resume)
    mock_nrgkick_api.set_charge_pause.return_value = {"charge_pause": 0}

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.nrgkick_test_charge_pause"},
        blocking=True,
    )

    # Note: set_charge_pause called twice now
    assert mock_nrgkick_api.set_charge_pause.call_count == 2
    mock_nrgkick_api.set_charge_pause.assert_called_with(False)

    state = hass.states.get("switch.nrgkick_test_charge_pause")
    assert state
    assert state.state == STATE_OFF


async def test_switch_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test error handling for switch."""
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
    mock_nrgkick_api.set_charge_pause.side_effect = NRGkickApiClientError("API Error")

    with pytest.raises(
        HomeAssistantError,
        match=r"Failed to set charge_pause to on\. API Error",
    ):
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.nrgkick_test_charge_pause"},
            blocking=True,
        )


async def test_switch_turn_off_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test error handling for switch turn off."""
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
    mock_nrgkick_api.set_charge_pause.side_effect = NRGkickApiClientError("API Error")

    with pytest.raises(
        HomeAssistantError,
        match=r"Failed to set charge_pause to off\. API Error",
    ):
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.nrgkick_test_charge_pause"},
            blocking=True,
        )
