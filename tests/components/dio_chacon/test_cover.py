"""Test the Dio Chacon Cover sensor."""

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

from tests.common import MockConfigEntry, snapshot_platform


async def test_cover_actions(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the Dio Chacon covers."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    entity = entity_registry.async_get("cover.shutter_mock_1")

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.shutter_mock_1")
    assert state.state == STATE_CLOSING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.shutter_mock_1")
    assert state.state == STATE_OPEN

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.shutter_mock_1")
    assert state.state == STATE_OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_POSITION: 25, ATTR_ENTITY_ID: entity.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.shutter_mock_1")
    assert state.state == STATE_OPENING


async def test_cover_callbacks(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the Dio Chacon covers."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get("cover.shutter_mock_1")
    assert entity.unique_id == "L4HActuator_idmock1"
    assert entity.entity_id == "cover.shutter_mock_1"

    # Server side callback tests
    # We find the callback method on the mock client
    callback_device_state_function: Callable = (
        mock_dio_chacon_client.set_callback_device_state_by_device.call_args[0][1]
    )

    # Define a method to simply call it
    async def _callback_device_state_function(
        openlevel: int,
        movement: str,
        id: str = "L4HActuator_idmock1",
        connected: bool = True,
    ) -> None:
        callback_device_state_function(
            {
                "id": id,
                "connected": connected,
                "openlevel": openlevel,
                "movement": movement,
            }
        )
        await hass.async_block_till_done()

    # And call it to effectively launch the callback as the server would do
    await _callback_device_state_function(79, "stop")
    state = hass.states.get("cover.shutter_mock_1")
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 79
    assert state.state == STATE_OPEN

    await _callback_device_state_function(90, "up")
    state = hass.states.get("cover.shutter_mock_1")
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 90
    assert state.state == STATE_OPENING

    await _callback_device_state_function(60, "down")
    state = hass.states.get("cover.shutter_mock_1")
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

    mock_config_entry.add_to_hass(hass)

    mock_dio_chacon_client.search_all_devices.return_value = None
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get("cover.shutter_mock_1")
    assert not entity
