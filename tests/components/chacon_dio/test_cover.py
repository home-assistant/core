"""Test the Chacon Dio cover."""

from collections.abc import Callable
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

COVER_ENTITY_ID = "cover.shutter_mock_1"


async def test_entities(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the Chacon Dio covers."""

    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_cover_actions(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the Chacon Dio covers."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_CLOSING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_OPEN

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_POSITION: 25, ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_OPENING


async def test_cover_callbacks(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the Chacon Dio covers."""

    await setup_integration(hass, mock_config_entry)

    # Server side callback tests
    # We find the callback method on the mock client
    callback_device_state_function: Callable = (
        mock_dio_chacon_client.set_callback_device_state_by_device.call_args[0][1]
    )

    # Define a method to simply call it
    async def _callback_device_state_function(open_level: int, movement: str) -> None:
        callback_device_state_function(
            {
                "id": "L4HActuator_idmock1",
                "connected": True,
                "openlevel": open_level,
                "movement": movement,
            }
        )
        await hass.async_block_till_done()

    # And call it to effectively launch the callback as the server would do
    await _callback_device_state_function(79, "stop")
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 79
    assert state.state == STATE_OPEN

    await _callback_device_state_function(90, "up")
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 90
    assert state.state == STATE_OPENING

    await _callback_device_state_function(60, "down")
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 60
    assert state.state == STATE_CLOSING


async def test_no_cover_found(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the cover absence."""

    mock_dio_chacon_client.search_all_devices.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.get(COVER_ENTITY_ID)
