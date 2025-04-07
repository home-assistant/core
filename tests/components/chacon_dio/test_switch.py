"""Test the Chacon Dio switch."""

from collections.abc import Callable
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

SWITCH_ENTITY_ID = "switch.switch_mock_1"

MOCK_SWITCH_DEVICE = {
    "L4HActuator_idmock1": {
        "id": "L4HActuator_idmock1",
        "name": "Switch mock 1",
        "type": "SWITCH_LIGHT",
        "model": "CERNwd-3B_1.0.6",
        "connected": True,
        "is_on": True,
    }
}


async def test_entities(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the Chacon Dio switches."""

    mock_dio_chacon_client.search_all_devices.return_value = MOCK_SWITCH_DEVICE

    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_actions(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the actions on the Chacon Dio switch."""

    mock_dio_chacon_client.search_all_devices.return_value = MOCK_SWITCH_DEVICE

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(SWITCH_ENTITY_ID)
    # turn off does not change directly the state, it is made by a server side callback.
    assert state.state == STATE_ON


async def test_switch_callbacks(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the callbacks on the Chacon Dio switches."""

    mock_dio_chacon_client.search_all_devices.return_value = MOCK_SWITCH_DEVICE

    await setup_integration(hass, mock_config_entry)

    # Server side callback tests
    # We find the callback method on the mock client
    callback_device_state_function: Callable = (
        mock_dio_chacon_client.set_callback_device_state_by_device.call_args[0][1]
    )

    # Define a method to simply call it
    async def _callback_device_state_function(is_on: bool) -> None:
        callback_device_state_function(
            {
                "id": "L4HActuator_idmock1",
                "connected": True,
                "is_on": is_on,
            }
        )
        await hass.async_block_till_done()

    # And call it to effectively launch the callback as the server would do
    await _callback_device_state_function(False)
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


async def test_no_switch_found(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the switch absence."""

    mock_dio_chacon_client.search_all_devices.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)
