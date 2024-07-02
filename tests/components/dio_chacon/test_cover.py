"""Test the Dio Chacon Cover sensor."""

from collections.abc import Callable
from unittest.mock import AsyncMock

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
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_cover_actions(
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

    state = hass.states.get("cover.shutter_mock_1")

    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 75
    assert state.attributes.get(ATTR_DEVICE_CLASS) == CoverDeviceClass.SHUTTER
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Shutter mock 1"
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        == CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
    )

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
    # And calls it to effectively launch the callback as the server would do
    callback_device_state_function(
        {
            "id": "L4HActuator_idmock1",
            "connected": True,
            "openlevel": 79,
            "movement": "stop",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.shutter_mock_1")
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 79
    assert state.state == STATE_OPEN

    callback_device_state_function(
        {
            "id": "L4HActuator_idmock1",
            "connected": True,
            "openlevel": 90,
            "movement": "up",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.shutter_mock_1")
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 90
    assert state.state == STATE_OPENING

    callback_device_state_function(
        {
            "id": "L4HActuator_idmock1",
            "connected": True,
            "openlevel": 60,
            "movement": "down",
        }
    )
    await hass.async_block_till_done()
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
