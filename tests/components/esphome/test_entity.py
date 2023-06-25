"""Test ESPHome binary sensors."""
from collections.abc import Awaitable, Callable
from typing import Any

from aioesphomeapi import (
    APIClient,
    BinarySensorInfo,
    BinarySensorState,
    EntityInfo,
    EntityState,
    UserService,
)

from homeassistant.const import ATTR_RESTORED, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDevice


async def test_entities_removed(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a generic binary_sensor where has_state is false."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        ),
        BinarySensorInfo(
            object_id="mybinary_sensor_to_be_removed",
            key=2,
            name="my binary_sensor to be removed",
            unique_id="mybinary_sensor_to_be_removed",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False),
    ]
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    entry = mock_device.entry
    entry_id = entry.entry_id
    storage_key = f"esphome.{entry_id}"
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is not None
    assert state.state == STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 2

    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.attributes[ATTR_RESTORED] is True
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is not None
    assert state.attributes[ATTR_RESTORED] is True

    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        entry=entry,
    )
    assert mock_device.entry.entry_id == entry_id
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is None
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 1
