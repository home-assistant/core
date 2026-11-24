"""Tests for the Lutron Homeworks Series 4 and 8 light."""

from unittest.mock import ANY, MagicMock

from pyhomeworks.pyhomeworks import HW_LIGHT_CHANGED
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_unordered import unordered
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    LightService,
    LightServiceArgument,
)
from homeassistant.const import STATE_OFF, STATE_ON, TargetKey
from homeassistant.core import HomeAssistant


async def test_light_attributes_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homeworks: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Homeworks light state changes."""
    entity_id = "light.foyer_sconces"
    mock_controller = MagicMock()
    mock_homeworks.return_value = mock_controller

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_homeworks.assert_called_once_with("192.168.0.1", 1234, ANY, None, None)
    hw_callback = mock_homeworks.mock_calls[0][1][2]

    assert len(mock_controller.request_dimmer_level.mock_calls) == 1
    assert mock_controller.request_dimmer_level.mock_calls[0][1] == ("[02:08:01:01]",)

    assert hass.states.async_entity_ids("light") == unordered([entity_id])

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state == snapshot

    hw_callback(HW_LIGHT_CHANGED, ["[02:08:01:01]", 50])
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state == snapshot


async def test_light_service_calls(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homeworks: MagicMock,
) -> None:
    """Test Homeworks light service call."""
    entity_id = "light.foyer_sconces"
    mock_controller = MagicMock()
    mock_homeworks.return_value = mock_controller

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids("light") == unordered([entity_id])

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_controller.fade_dim.assert_called_with(0.0, 1.0, 0, "[02:08:01:01]")

    # The light's brightness is unknown, turning it on should set it to max
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_controller.fade_dim.assert_called_with(100.0, 1.0, 0, "[02:08:01:01]")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.BRIGHTNESS: 127},
        blocking=True,
    )
    mock_controller.fade_dim.assert_called_with(
        pytest.approx(49.8, abs=0.1), 1.0, 0, "[02:08:01:01]"
    )


async def test_light_restore_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homeworks: MagicMock,
) -> None:
    """Test Homeworks light service call."""
    entity_id = "light.foyer_sconces"
    mock_controller = MagicMock()
    mock_homeworks.return_value = mock_controller

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_homeworks.assert_called_once_with("192.168.0.1", 1234, ANY, None, None)
    hw_callback = mock_homeworks.mock_calls[0][1][2]

    assert hass.states.async_entity_ids("light") == unordered([entity_id])

    hw_callback(HW_LIGHT_CHANGED, ["[02:08:01:01]", 50])
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 127

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_controller.fade_dim.assert_called_with(
        pytest.approx(49.8, abs=0.1), 1.0, 0, "[02:08:01:01]"
    )
