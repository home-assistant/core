"""Test Homee entity in general."""

from unittest.mock import MagicMock

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry


async def test_entity_connection_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if loss of connection is sensed correctly."""
    mock_homee.nodes = [build_mock_node("sensors.json")]
    await setup_integration(hass, mock_config_entry)

    states = hass.states.get("sensor.test_multisensor_energy_1")
    assert states.state is not STATE_UNAVAILABLE

    mock_homee.add_connection_listener.call_args_list[1][0][0](False)
    await hass.async_block_till_done()

    states = hass.states.get("sensor.test_multisensor_energy_1")
    assert states.state is STATE_UNAVAILABLE

    mock_homee.add_connection_listener.call_args_list[1][0][0](True)
    await hass.async_block_till_done()

    states = hass.states.get("sensor.test_multisensor_energy_1")
    assert states.state is not STATE_UNAVAILABLE


async def test_node_entity_connection_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if loss of connection is sensed correctly."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    await setup_integration(hass, mock_config_entry)

    states = hass.states.get("cover.test_cover")
    assert states.state != STATE_UNAVAILABLE

    mock_homee.add_connection_listener.call_args_list[1][0][0](False)
    await hass.async_block_till_done()

    states = hass.states.get("cover.test_cover")
    assert states.state == STATE_UNAVAILABLE

    mock_homee.add_connection_listener.call_args_list[1][0][0](True)
    await hass.async_block_till_done()

    states = hass.states.get("cover.test_cover")
    assert states.state != STATE_UNAVAILABLE


async def test_entity_update_action(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the update_entity action for a HomeeEntity."""
    mock_homee.nodes = [build_mock_node("sensors.json")]
    await setup_integration(hass, mock_config_entry)
    await async_setup_component(hass, HA_DOMAIN, {})

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "sensor.test_multisensor_temperature"},
        blocking=True,
    )

    mock_homee.update_attribute.assert_called_once_with(1, 23)


async def test_node_entity_update_action(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the update_entity action for a HomeeEntity."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    await setup_integration(hass, mock_config_entry)
    await async_setup_component(hass, HA_DOMAIN, {})

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )

    mock_homee.update_node.assert_called_once_with(3)
