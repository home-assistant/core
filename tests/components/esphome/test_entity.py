"""Test ESPHome binary sensors."""

import asyncio
from dataclasses import asdict
from typing import Any
from unittest.mock import AsyncMock

from aioesphomeapi import (
    APIClient,
    BinarySensorInfo,
    BinarySensorState,
    DeviceInfo,
    SensorInfo,
    SensorState,
    build_unique_id,
)
import pytest

from homeassistant.components.esphome import DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_RESTORED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .conftest import MockESPHomeDevice, MockESPHomeDeviceType


async def test_entities_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entities are removed when static info changes."""
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
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is not None
    assert state.state == STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 2

    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.attributes[ATTR_RESTORED] is True
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is not None
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_mybinary_sensor_to_be_removed"
    )
    assert reg_entry is not None
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
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is None
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_mybinary_sensor_to_be_removed"
    )
    assert reg_entry is None
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 1


async def test_entities_removed_after_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entities and their registry entry are removed when static info changes after a reload."""
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
    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    entry = mock_device.entry
    entry_id = entry.entry_id
    storage_key = f"esphome.{entry_id}"
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is not None
    assert state.state == STATE_ON

    reg_entry = entity_registry.async_get(
        "binary_sensor.test_mybinary_sensor_to_be_removed"
    )
    assert reg_entry is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 2

    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.attributes[ATTR_RESTORED] is True
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is not None
    assert state.attributes[ATTR_RESTORED] is True

    reg_entry = entity_registry.async_get(
        "binary_sensor.test_mybinary_sensor_to_be_removed"
    )
    assert reg_entry is not None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 2

    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert ATTR_RESTORED not in state.attributes
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is not None
    assert ATTR_RESTORED not in state.attributes
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_mybinary_sensor_to_be_removed"
    )
    assert reg_entry is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        ),
    ]
    mock_device.client.list_entities_services = AsyncMock(
        return_value=(entity_info, user_service)
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    on_future = hass.loop.create_future()

    @callback
    def _async_wait_for_on(event: Event[EventStateChangedData]) -> None:
        if event.data["new_state"].state == STATE_ON:
            on_future.set_result(None)

    async_track_state_change_event(
        hass, ["binary_sensor.test_mybinary_sensor"], _async_wait_for_on
    )
    await hass.async_block_till_done()
    async with asyncio.timeout(2):
        await on_future

    assert mock_device.entry.entry_id == entry_id
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is None

    await hass.async_block_till_done()

    reg_entry = entity_registry.async_get(
        "binary_sensor.test_mybinary_sensor_to_be_removed"
    )
    assert reg_entry is None
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 1


async def test_entities_for_entire_platform_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test removing all entities for a specific platform when static info changes."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor_to_be_removed",
            key=1,
            name="my binary_sensor to be removed",
            unique_id="mybinary_sensor_to_be_removed",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
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
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is not None
    assert state.state == STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 1

    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is not None
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_mybinary_sensor_to_be_removed"
    )
    assert reg_entry is not None
    assert state.attributes[ATTR_RESTORED] is True

    entity_info = []
    states = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        entry=entry,
    )
    assert mock_device.entry.entry_id == entry_id
    state = hass.states.get("binary_sensor.test_mybinary_sensor_to_be_removed")
    assert state is None
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_mybinary_sensor_to_be_removed"
    )
    assert reg_entry is None
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 0


async def test_entity_info_object_ids(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test how object ids affect entity id."""
    entity_info = [
        BinarySensorInfo(
            object_id="object_id_is_used",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_object_id_is_used")
    assert state is not None


async def test_deep_sleep_device(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a deep sleep device."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        ),
        SensorInfo(
            object_id="my_sensor",
            key=3,
            name="my sensor",
            unique_id="my_sensor",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False),
        SensorState(key=3, state=123.0, missing_state=False),
    ]
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"has_deep_sleep": True},
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "123"

    await mock_device.mock_disconnect(False)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await mock_device.mock_connect()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "123"

    await mock_device.mock_disconnect(True)
    await hass.async_block_till_done()
    await mock_device.mock_connect()
    await hass.async_block_till_done()
    mock_device.set_state(BinarySensorState(key=1, state=False, missing_state=False))
    mock_device.set_state(SensorState(key=3, state=56, missing_state=False))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_OFF
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "56"

    await mock_device.mock_disconnect(True)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_OFF
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "56"

    await mock_device.mock_connect()
    await hass.async_block_till_done()
    await mock_device.mock_disconnect(False)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await mock_device.mock_connect()
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    # Verify we do not dispatch any more state updates or
    # availability updates after the stop event is fired
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_esphome_device_without_friendly_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device without friendly_name set."""
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
        BinarySensorState(key=2, state=True, missing_state=False),
    ]
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"friendly_name": None},
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_entity_without_name_device_with_friendly_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test name and entity_id for a device a friendly name and an entity without a name."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="",
            unique_id="my_binary_sensor",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"friendly_name": "The Best Mixer", "name": "mixer"},
    )
    state = hass.states.get("binary_sensor.mixer")
    assert state is not None
    assert state.state == STATE_ON
    # Make sure we have set the name to `None` as otherwise
    # the friendly_name will be "The Best Mixer "
    assert state.attributes[ATTR_FRIENDLY_NAME] == "The Best Mixer"


@pytest.mark.usefixtures("hass_storage")
async def test_entity_id_preserved_on_upgrade(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity_id is preserved on upgrade."""
    entity_info = [
        BinarySensorInfo(
            object_id="my",
            key=1,
            name="my",
            unique_id="binary_sensor_my",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    user_service = []
    assert (
        build_unique_id("11:22:33:44:55:AA", entity_info[0])
        == "11:22:33:44:55:AA-binary_sensor-my"
    )

    entry = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        "11:22:33:44:55:AA-binary_sensor-my",
        suggested_object_id="should_not_change",
    )
    assert entry.entity_id == "binary_sensor.should_not_change"
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"friendly_name": "The Best Mixer", "name": "mixer"},
    )
    state = hass.states.get("binary_sensor.should_not_change")
    assert state is not None


@pytest.mark.usefixtures("hass_storage")
async def test_entity_id_preserved_on_upgrade_old_format_entity_id(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity_id is preserved on upgrade from old format."""
    entity_info = [
        BinarySensorInfo(
            object_id="my",
            key=1,
            name="my",
            unique_id="binary_sensor_my",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    user_service = []
    assert (
        build_unique_id("11:22:33:44:55:AA", entity_info[0])
        == "11:22:33:44:55:AA-binary_sensor-my"
    )

    entry = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        "11:22:33:44:55:AA-binary_sensor-my",
        suggested_object_id="my",
    )
    assert entry.entity_id == "binary_sensor.my"
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"name": "mixer"},
    )
    state = hass.states.get("binary_sensor.my")
    assert state is not None


async def test_entity_id_preserved_on_upgrade_when_in_storage(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: MockESPHomeDeviceType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity_id is preserved on upgrade with user defined entity_id."""
    entity_info = [
        BinarySensorInfo(
            object_id="my",
            key=1,
            name="my",
            unique_id="binary_sensor_my",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    user_service = []
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"friendly_name": "The Best Mixer", "name": "mixer"},
    )
    state = hass.states.get("binary_sensor.mixer_my")
    assert state is not None
    # now rename the entity
    ent_reg_entry = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        "11:22:33:44:55:AA-binary_sensor-my",
    )
    entity_registry.async_update_entity(
        ent_reg_entry.entity_id,
        new_entity_id="binary_sensor.user_named",
    )
    await hass.config_entries.async_unload(device.entry.entry_id)
    await hass.async_block_till_done()
    entry = device.entry
    entry_id = entry.entry_id
    storage_key = f"esphome.{entry_id}"
    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 1
    binary_sensor_data: dict[str, Any] = hass_storage[storage_key]["data"][
        "binary_sensor"
    ][0]
    assert binary_sensor_data["name"] == "my"
    assert binary_sensor_data["object_id"] == "my"
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        entry=entry,
        device_info={"friendly_name": "The Best Mixer", "name": "mixer"},
    )
    state = hass.states.get("binary_sensor.user_named")
    assert state is not None


async def test_deep_sleep_added_after_setup(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test deep sleep added after setup."""
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[
            BinarySensorInfo(
                object_id="test",
                key=1,
                name="test",
                unique_id="test",
            ),
        ],
        user_service=[],
        states=[
            BinarySensorState(key=1, state=True, missing_state=False),
        ],
        device_info={"has_deep_sleep": False},
    )

    entity_id = "binary_sensor.test_test"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await mock_device.mock_disconnect(expected_disconnect=True)

    # No deep sleep, should be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await mock_device.mock_connect()

    # reconnect, should be available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await mock_device.mock_disconnect(expected_disconnect=True)
    new_device_info = DeviceInfo(
        **{**asdict(mock_device.device_info), "has_deep_sleep": True}
    )
    mock_device.client.device_info = AsyncMock(return_value=new_device_info)
    mock_device.device_info = new_device_info

    await mock_device.mock_connect()

    # Now disconnect that deep sleep is set in device info
    await mock_device.mock_disconnect(expected_disconnect=True)

    # Deep sleep, should be available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
