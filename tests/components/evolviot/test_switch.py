"""Test the EvolvIOT switch platform."""

import pytest

from homeassistant.components.evolviot.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import UNIQUE_ID, MockEvolvIOTWebSocket, evolviot_data

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration")
async def test_switch_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch setup from WebSocket ready data."""
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("setup_integration")
async def test_switch_push_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test WebSocket state pushes update the switch."""
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)

    await mock_websocket.emit_state("on")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_ON


async def test_switch_available_during_websocket_reconnect(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_integration: MockConfigEntry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test a switch remains available while its WebSocket reconnects."""
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)
    mock_websocket.closed = True
    setup_integration.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("setup_integration")
async def test_switch_sends_commands(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test switch commands are sent through pyevolviot."""
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_websocket.commands[-1] == ("switch.evolviot_switch", "turn_on")
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_websocket.commands[-1] == ("switch.evolviot_switch", "turn_off")
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_connect_websocket")
async def test_switch_classified_by_device_context(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test Home Assistant classifies a supported control as a switch."""
    mock_websocket.data = evolviot_data(domain="light")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)


@pytest.mark.usefixtures("mock_connect_websocket")
async def test_unsupported_control_not_added(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test an unsupported device control is not added as a switch."""
    mock_websocket.data = evolviot_data(model="Light")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)
