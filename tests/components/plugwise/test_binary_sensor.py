"""Tests for the Plugwise binary_sensor integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        ("binary_sensor.opentherm_secondary_boiler_state", STATE_OFF),
        ("binary_sensor.opentherm_dhw_state", STATE_OFF),
        ("binary_sensor.opentherm_heating", STATE_ON),
        ("binary_sensor.opentherm_cooling_enabled", STATE_OFF),
        ("binary_sensor.opentherm_compressor_state", STATE_ON),
    ],
)
async def test_anna_climate_binary_sensor_entities(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    init_integration: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test creation of climate related binary_sensor entities."""
    state = hass.states.get(entity_id)
    assert state.state == expected_state


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
async def test_anna_climate_binary_sensor_change(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test change of climate related binary_sensor entities."""
    hass.states.async_set("binary_sensor.opentherm_dhw_state", STATE_ON, {})
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.opentherm_dhw_state")
    assert state
    assert state.state == STATE_ON

    await async_update_entity(hass, "binary_sensor.opentherm_dhw_state")

    state = hass.states.get("binary_sensor.opentherm_dhw_state")
    assert state
    assert state.state == STATE_OFF


async def test_adam_climate_binary_sensor_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test of a climate related plugwise-notification binary_sensor."""
    state = hass.states.get("binary_sensor.adam_plugwise_notification")
    assert state
    assert state.state == STATE_ON
    assert "warning_msg" in state.attributes
    assert "unreachable" in state.attributes["warning_msg"][0]
    assert not state.attributes.get("error_msg")
    assert not state.attributes.get("other_msg")


@pytest.mark.parametrize("chosen_env", ["p1v4_442_triple"], indirect=True)
@pytest.mark.parametrize(
    "gateway_id", ["03e65b16e4b247a29ae0d75a78cb492e"], indirect=True
)
async def test_p1_binary_sensor_entity(
    hass: HomeAssistant, mock_smile_p1: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test of a Smile P1 related plugwise-notification binary_sensor."""
    state = hass.states.get("binary_sensor.smile_p1_plugwise_notification")
    assert state
    assert state.state == STATE_ON
    assert "warning_msg" in state.attributes
    assert "connected" in state.attributes["warning_msg"][0]
