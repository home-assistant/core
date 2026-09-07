"""Test ESPHome binary sensors."""

import asyncio
from dataclasses import asdict
import logging
from typing import Any
from unittest.mock import AsyncMock

from aioesphomeapi import (
    APIClient,
    BinarySensorInfo,
    BinarySensorState,
    DeviceInfo,
    SensorInfo,
    SensorState,
    SubDeviceInfo,
    build_device_unique_id,
    build_unique_id,
)
import pytest

from homeassistant.components.esphome import DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_RESTORED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)

from .conftest import (
    MockESPHomeDevice,
    MockESPHomeDeviceType,
    MockGenericDeviceEntryType,
    reconnect_with_updated_entity_info,
)


def track_entity_registry_actions(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Track entity registry actions for an entity."""
    events: list[str] = []

    @callback
    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Add entity registry updated event to the list."""
        events.append(event.data["action"])

    async_track_entity_registry_updated_event(hass, entity_id, add_event)

    return events


def _two_binary_sensor_setup() -> tuple[
    list[BinarySensorInfo], list[BinarySensorState]
]:
    """Return two binary sensors and their states for re-key tests."""
    entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=1,
            name="Sensor One",
        ),
        BinarySensorInfo(
            object_id="sensor_two",
            key=2,
            name="Sensor Two",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False),
    ]
    return entity_info, states


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
        ),
        BinarySensorInfo(
            object_id="mybinary_sensor_to_be_removed",
            key=2,
            name="my binary_sensor to be removed",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False),
    ]
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
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
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_my_binary_sensor_to_be_removed"
    )
    assert reg_entry is not None
    assert state.attributes[ATTR_RESTORED] is True

    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
        entry=entry,
    )
    assert mock_device.entry.entry_id == entry_id
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is None
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_my_binary_sensor_to_be_removed"
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
    """Test entities are removed when static info changes after reload."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
        ),
        BinarySensorInfo(
            object_id="mybinary_sensor_to_be_removed",
            key=2,
            name="my binary_sensor to be removed",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False),
    ]
    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
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

    reg_entry = entity_registry.async_get(
        "binary_sensor.test_my_binary_sensor_to_be_removed"
    )
    assert reg_entry is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 2

    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.attributes[ATTR_RESTORED] is True
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is not None
    assert state.attributes[ATTR_RESTORED] is True

    reg_entry = entity_registry.async_get(
        "binary_sensor.test_my_binary_sensor_to_be_removed"
    )
    assert reg_entry is not None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 2

    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert ATTR_RESTORED not in state.attributes
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is not None
    assert ATTR_RESTORED not in state.attributes
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_my_binary_sensor_to_be_removed"
    )
    assert reg_entry is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
        ),
    ]
    mock_device.client.list_entities_services = AsyncMock(
        return_value=(entity_info, [])
    )
    mock_device.client.device_info_and_list_entities = AsyncMock(
        return_value=(mock_device.device_info, entity_info, [])
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    on_future = hass.loop.create_future()

    @callback
    def _async_wait_for_on(event: Event[EventStateChangedData]) -> None:
        if event.data["new_state"].state == STATE_ON:
            on_future.set_result(None)

    async_track_state_change_event(
        hass, ["binary_sensor.test_my_binary_sensor"], _async_wait_for_on
    )
    await hass.async_block_till_done()
    async with asyncio.timeout(2):
        await on_future

    assert mock_device.entry.entry_id == entry_id
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is None

    await hass.async_block_till_done()

    reg_entry = entity_registry.async_get(
        "binary_sensor.test_my_binary_sensor_to_be_removed"
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
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    entry = mock_device.entry
    entry_id = entry.entry_id
    storage_key = f"esphome.{entry_id}"
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is not None
    assert state.state == STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass_storage[storage_key]["data"]["binary_sensor"]) == 1

    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is not None
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_my_binary_sensor_to_be_removed"
    )
    assert reg_entry is not None
    assert state.attributes[ATTR_RESTORED] is True

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
    )
    assert mock_device.entry.entry_id == entry_id
    state = hass.states.get("binary_sensor.test_my_binary_sensor_to_be_removed")
    assert state is None
    reg_entry = entity_registry.async_get(
        "binary_sensor.test_my_binary_sensor_to_be_removed"
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
        )
    ]
    states = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
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
        ),
        SensorInfo(
            object_id="my_sensor",
            key=3,
            name="my sensor",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False),
        SensorState(key=3, state=123.0, missing_state=False),
    ]
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
        device_info={"has_deep_sleep": True},
    )
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "123.0"

    await mock_device.mock_disconnect(False)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await mock_device.mock_connect()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "123.0"

    await mock_device.mock_disconnect(True)
    await hass.async_block_till_done()
    await mock_device.mock_connect()
    await hass.async_block_till_done()
    mock_device.set_state(BinarySensorState(key=1, state=False, missing_state=False))
    mock_device.set_state(SensorState(key=3, state=56, missing_state=False))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_OFF
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "56"

    await mock_device.mock_disconnect(True)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_OFF
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "56"

    await mock_device.mock_connect()
    await hass.async_block_till_done()
    await mock_device.mock_disconnect(False)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await mock_device.mock_connect()
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    # Verify we do not dispatch any more state updates or
    # availability updates after the stop event is fired
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
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
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False),
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
        device_info={"friendly_name": None},
    )
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_entity_without_name_device_with_friendly_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test name and entity_id for device with friendly name."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
        device_info={"friendly_name": "The Best Mixer", "name": "mixer"},
    )
    state = hass.states.get("binary_sensor.the_best_mixer")
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
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
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
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
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
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
        device_info={"friendly_name": "The Best Mixer", "name": "mixer"},
    )
    state = hass.states.get("binary_sensor.the_best_mixer_my")
    assert state is not None
    # now rename the entity
    ent_reg_entry = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        "11:22:33:44:55:AA/0/binary_sensor/my",
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
            ),
        ],
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
    mock_device.client.device_info_and_list_entities = AsyncMock(
        return_value=(
            new_device_info,
            mock_device.client.list_entities_services.return_value[0],
            mock_device.client.list_entities_services.return_value[1],
        )
    )
    mock_device.device_info = new_device_info

    await mock_device.mock_connect()

    # Now disconnect that deep sleep is set in device info
    await mock_device.mock_disconnect(expected_disconnect=True)

    # Deep sleep, should be available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


async def test_entity_assignment_to_sub_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entities are assigned to correct sub devices."""
    # Define sub devices
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="Motion Sensor", area_id=0),
        SubDeviceInfo(device_id=22222222, name="Door Sensor", area_id=0),
    ]

    device_info = {
        "devices": sub_devices,
    }

    # Create entities that belong to different devices
    entity_info = [
        # Entity for main device (device_id=0)
        BinarySensorInfo(
            object_id="main_sensor",
            key=1,
            name="Main Sensor",
            device_id=0,
        ),
        # Entity for sub device 1
        BinarySensorInfo(
            object_id="motion",
            key=2,
            name="Motion",
            device_id=11111111,
        ),
        # Entity for sub device 2
        BinarySensorInfo(
            object_id="door",
            key=3,
            name="Door",
            device_id=22222222,
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False, device_id=0),
        BinarySensorState(key=2, state=False, missing_state=False, device_id=11111111),
        BinarySensorState(key=3, state=True, missing_state=False, device_id=22222222),
    ]

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Check main device
    main_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address),
        device.entry.entry_id,
    )
    assert main_device is not None

    # Check entities are assigned to correct devices
    main_sensor = entity_registry.async_get("binary_sensor.test_main_sensor")
    assert main_sensor is not None
    assert main_sensor.device_id == main_device.id

    # Check sub device 1 entity
    sub_device_1 = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_11111111"), device.entry.entry_id
    )
    assert sub_device_1 is not None

    motion_sensor = entity_registry.async_get("binary_sensor.motion_sensor_motion")
    assert motion_sensor is not None
    assert motion_sensor.device_id == sub_device_1.id

    # Check sub device 2 entity
    sub_device_2 = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_22222222"), device.entry.entry_id
    )
    assert sub_device_2 is not None

    door_sensor = entity_registry.async_get("binary_sensor.door_sensor_door")
    assert door_sensor is not None
    assert door_sensor.device_id == sub_device_2.id

    # Check states
    assert hass.states.get("binary_sensor.test_main_sensor").state == STATE_ON
    assert hass.states.get("binary_sensor.motion_sensor_motion").state == STATE_OFF
    assert hass.states.get("binary_sensor.door_sensor_door").state == STATE_ON

    # Check entity friendly names
    # Main device entity should have: "{device_name} {entity_name}"
    main_sensor_state = hass.states.get("binary_sensor.test_main_sensor")
    assert main_sensor_state.attributes[ATTR_FRIENDLY_NAME] == "Test Main Sensor"

    # Sub device 1 entity should have: "Motion Sensor Motion"
    motion_sensor_state = hass.states.get("binary_sensor.motion_sensor_motion")
    assert motion_sensor_state.attributes[ATTR_FRIENDLY_NAME] == "Motion Sensor Motion"

    # Sub device 2 entity should have: "Door Sensor Door"
    door_sensor_state = hass.states.get("binary_sensor.door_sensor_door")
    assert door_sensor_state.attributes[ATTR_FRIENDLY_NAME] == "Door Sensor Door"


async def test_entity_friendly_names_with_empty_device_names(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entity friendly names when sub-devices have empty names."""
    # Define sub devices with different name scenarios
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="", area_id=0),  # Empty name
        SubDeviceInfo(
            device_id=22222222, name="Kitchen Light", area_id=0
        ),  # Valid name
    ]

    device_info = {
        "devices": sub_devices,
        "friendly_name": "Main Device",
    }

    # Entity on sub-device with empty name
    entity_info = [
        BinarySensorInfo(
            object_id="motion",
            key=1,
            name="Motion Detected",
            device_id=11111111,
        ),
        # Entity on sub-device with valid name
        BinarySensorInfo(
            object_id="status",
            key=2,
            name="Status",
            device_id=22222222,
        ),
        # Entity with empty name on sub-device with valid name
        BinarySensorInfo(
            object_id="sensor",
            key=3,
            name="",  # Empty entity name
            device_id=22222222,
        ),
        # Entity on main device
        BinarySensorInfo(
            object_id="main_status",
            key=4,
            name="Main Status",
            device_id=0,
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=False, missing_state=False),
        BinarySensorState(key=3, state=True, missing_state=False),
        BinarySensorState(key=4, state=True, missing_state=False),
    ]

    await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Check entity friendly name on sub-device with empty name
    # Since sub device has empty name, it falls back to main device name "Main device"
    state_1 = hass.states.get("binary_sensor.main_device_motion_detected")
    assert state_1 is not None
    # With has_entity_name, friendly name is "{device_name} {entity_name}"
    # Since sub-device falls back to main device name: "Main Device Motion Detected"
    assert state_1.attributes[ATTR_FRIENDLY_NAME] == "Main Device Motion Detected"

    # Check entity friendly name on sub-device with valid name
    state_2 = hass.states.get("binary_sensor.kitchen_light_status")
    assert state_2 is not None
    # Device has name "Kitchen Light", entity has name "Status"
    assert state_2.attributes[ATTR_FRIENDLY_NAME] == "Kitchen Light Status"

    # Test entity with empty name on sub-device
    state_3 = hass.states.get("binary_sensor.kitchen_light")
    assert state_3 is not None
    # Entity has empty name, so friendly name is just the device name
    assert state_3.attributes[ATTR_FRIENDLY_NAME] == "Kitchen Light"

    # Test entity on main device
    state_4 = hass.states.get("binary_sensor.main_device_main_status")
    assert state_4 is not None
    assert state_4.attributes[ATTR_FRIENDLY_NAME] == "Main Device Main Status"


async def test_entity_switches_between_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test that entities can switch between devices correctly."""
    # Define sub devices
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="Sub Device 1", area_id=0),
        SubDeviceInfo(device_id=22222222, name="Sub Device 2", area_id=0),
    ]

    device_info = {
        "devices": sub_devices,
    }

    # Create initial entity assigned to main device (no device_id)
    entity_info = [
        BinarySensorInfo(
            object_id="sensor",
            key=1,
            name="Test Sensor",
            # device_id omitted - entity belongs to main device
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False, device_id=0),
    ]

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Verify entity is on main device
    main_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address),
        device.entry.entry_id,
    )
    assert main_device is not None

    sensor_entity = entity_registry.async_get("binary_sensor.test_test_sensor")
    assert sensor_entity is not None
    assert sensor_entity.device_id == main_device.id

    # Test 1: Main device → Sub device 1
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor",
            key=1,
            name="Test Sensor",
            device_id=11111111,  # Now on sub device 1
        ),
    ]

    # Update the entity info by changing what the mock returns
    mock_client.list_entities_services = AsyncMock(
        return_value=(updated_entity_info, [])
    )
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, updated_entity_info, [])
    )
    # Trigger a reconnect to simulate the entity info update
    await device.mock_disconnect(expected_disconnect=False)
    await device.mock_connect()

    # Verify entity is now on sub device 1
    sub_device_1 = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_11111111"), device.entry.entry_id
    )
    assert sub_device_1 is not None

    sensor_entity = entity_registry.async_get("binary_sensor.test_test_sensor")
    assert sensor_entity is not None
    assert sensor_entity.device_id == sub_device_1.id

    # Test 2: Sub device 1 → Sub device 2
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor",
            key=1,
            name="Test Sensor",
            device_id=22222222,  # Now on sub device 2
        ),
    ]

    mock_client.list_entities_services = AsyncMock(
        return_value=(updated_entity_info, [])
    )
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, updated_entity_info, [])
    )
    await device.mock_disconnect(expected_disconnect=False)
    await device.mock_connect()

    # Verify entity is now on sub device 2
    sub_device_2 = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_22222222"), device.entry.entry_id
    )
    assert sub_device_2 is not None

    sensor_entity = entity_registry.async_get("binary_sensor.test_test_sensor")
    assert sensor_entity is not None
    assert sensor_entity.device_id == sub_device_2.id

    # Test 3: Sub device 2 → Main device
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor",
            key=1,
            name="Test Sensor",
            # device_id omitted - back to main device
        ),
    ]

    mock_client.list_entities_services = AsyncMock(
        return_value=(updated_entity_info, [])
    )
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, updated_entity_info, [])
    )
    await device.mock_disconnect(expected_disconnect=False)
    await device.mock_connect()

    # Verify entity is back on main device
    sensor_entity = entity_registry.async_get("binary_sensor.test_test_sensor")
    assert sensor_entity is not None
    assert sensor_entity.device_id == main_device.id


async def test_entity_id_uses_sub_device_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test that entity_id uses sub device name when entity belongs to sub device."""
    # Define sub devices
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="motion_sensor", area_id=0),
        SubDeviceInfo(device_id=22222222, name="door_sensor", area_id=0),
    ]

    device_info = {
        "devices": sub_devices,
        "name": "main_device",
        "friendly_name": "Main Device",
    }

    # Create entities that belong to different devices
    entity_info = [
        # Entity for main device (device_id=0)
        BinarySensorInfo(
            object_id="main_sensor",
            key=1,
            name="Main Sensor",
            device_id=0,
        ),
        # Entity for sub device 1
        BinarySensorInfo(
            object_id="motion",
            key=2,
            name="Motion",
            device_id=11111111,
        ),
        # Entity for sub device 2
        BinarySensorInfo(
            object_id="door",
            key=3,
            name="Door",
            device_id=22222222,
        ),
        # Entity without name on sub device
        BinarySensorInfo(
            object_id="sensor_no_name",
            key=4,
            name="",
            device_id=11111111,
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=False, missing_state=False),
        BinarySensorState(key=3, state=True, missing_state=False),
        BinarySensorState(key=4, state=True, missing_state=False),
    ]

    await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Check entity_id for main device entity
    # Should be: binary_sensor.{main_device_name}_{object_id}
    assert hass.states.get("binary_sensor.main_device_main_sensor") is not None

    # Check entity_id for sub device 1 entity
    # Should be: binary_sensor.{sub_device_name}_{object_id}
    assert hass.states.get("binary_sensor.motion_sensor_motion") is not None

    # Check entity_id for sub device 2 entity
    # Should be: binary_sensor.{sub_device_name}_{object_id}
    assert hass.states.get("binary_sensor.door_sensor_door") is not None

    # Check entity_id for entity without name on sub device
    # Should be: binary_sensor.{sub_device_name}
    assert hass.states.get("binary_sensor.motion_sensor") is not None


async def test_entity_id_with_empty_sub_device_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entity_id when sub device has empty name."""
    # Define sub device with empty name
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="", area_id=0),  # Empty name
    ]

    device_info = {
        "devices": sub_devices,
        "name": "main_device",
        "friendly_name": "Main Device",
    }

    # Create entity on sub device with empty name
    entity_info = [
        BinarySensorInfo(
            object_id="sensor",
            key=1,
            name="Sensor",
            device_id=11111111,
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]

    await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # When sub device has empty name, entity_id should use main device name
    # Should be: binary_sensor.{main_device_name}_{object_id}
    assert hass.states.get("binary_sensor.main_device_sensor") is not None


async def test_legacy_unique_id_migrated_to_v3_sub_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a legacy sub-device unique id is migrated to the version 3 format."""
    sub_devices = [
        SubDeviceInfo(device_id=22222222, name="kitchen_controller", area_id=0),
    ]
    device_info = {"name": "test", "devices": sub_devices}
    entity_info = [
        BinarySensorInfo(
            object_id="temperature",
            key=1,
            name="Temperature",
            device_id=22222222,
        ),
    ]
    states = [BinarySensorState(key=1, state=True, missing_state=False)]

    # Seed a registry entry in the legacy format with the @device_id suffix
    legacy_entry = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        "11:22:33:44:55:AA-binary_sensor-temperature@22222222",
        suggested_object_id="kitchen_controller_temperature",
    )

    await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    entity_entry = entity_registry.async_get(legacy_entry.entity_id)
    assert entity_entry is not None
    # The legacy id is renamed to version 3, keeping the same entity
    assert (
        entity_entry.unique_id == "11:22:33:44:55:AA/22222222/binary_sensor/Temperature"
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR,
            DOMAIN,
            "11:22:33:44:55:AA-binary_sensor-temperature@22222222",
        )
        is None
    )


async def test_unique_id_migration_when_entity_moves_between_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test unique_id is migrated when entity moves between devices."""
    # Initial setup: entity on main device
    device_info = {
        "name": "test",
        "devices": [],  # No sub-devices initially
    }

    # Entity on main device
    entity_info = [
        BinarySensorInfo(
            object_id="temperature",
            key=1,
            name="Temperature",  # This field is not used by the integration
            device_id=0,  # Main device
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Check initial entity
    state = hass.states.get("binary_sensor.test_temperature")
    assert state is not None

    # Get the entity from registry
    entity_entry = entity_registry.async_get("binary_sensor.test_temperature")
    assert entity_entry is not None
    initial_unique_id = entity_entry.unique_id
    # Main device entities use device_id 0 in the unique id
    assert "/0/" in initial_unique_id

    # Add sub-device to device info
    sub_devices = [
        SubDeviceInfo(device_id=22222222, name="kitchen_controller", area_id=0),
    ]

    # Get the config entry from hass
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    # Build device_id_to_name mapping like manager.py does
    entry_data = entry.runtime_data
    entry_data.device_id_to_name = {
        sub_device.device_id: sub_device.name for sub_device in sub_devices
    }

    # Create a new DeviceInfo with sub-devices since it's frozen
    # Get the current device info and convert to dict
    current_device_info = mock_client.device_info.return_value
    device_info_dict = asdict(current_device_info)

    # Update the devices list
    device_info_dict["devices"] = sub_devices

    # Create new DeviceInfo with updated devices
    new_device_info = DeviceInfo(**device_info_dict)

    # Update mock_client to return new device info
    mock_client.device_info.return_value = new_device_info

    # Update entity info - same key and object_id but now on sub-device
    new_entity_info = [
        BinarySensorInfo(
            object_id="temperature",  # Same object_id
            key=1,  # Same key - this is what identifies the entity
            name="Temperature",  # This field is not used
            device_id=22222222,  # Now on sub-device
        ),
    ]

    # Update the entity info by changing what the mock returns
    mock_client.list_entities_services = AsyncMock(return_value=(new_entity_info, []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, new_entity_info, [])
    )

    # Trigger a reconnect to simulate the entity info update
    await device.mock_disconnect(expected_disconnect=False)
    await device.mock_connect()

    # Wait for entity to be updated
    await hass.async_block_till_done()

    # The entity_id doesn't change when moving between devices,
    # only the device segment of the unique_id changes
    state = hass.states.get("binary_sensor.test_temperature")
    assert state is not None

    # Get updated entity from registry - entity_id should be the same
    entity_entry = entity_registry.async_get("binary_sensor.test_temperature")
    assert entity_entry is not None

    # Unique ID device segment should now be the sub-device id
    expected_unique_id = initial_unique_id.replace("/0/", "/22222222/")
    assert entity_entry.unique_id == expected_unique_id

    # Entity should now be associated with the sub-device
    sub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_22222222"), device.entry.entry_id
    )
    assert sub_device is not None
    assert entity_entry.device_id == sub_device.id


async def test_unique_id_migration_sub_device_to_main_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test unique_id is migrated when entity moves to main device."""
    # Initial setup: entity on sub-device
    sub_devices = [
        SubDeviceInfo(device_id=22222222, name="kitchen_controller", area_id=0),
    ]

    device_info = {
        "name": "test",
        "devices": sub_devices,
    }

    # Entity on sub-device
    entity_info = [
        BinarySensorInfo(
            object_id="temperature",
            key=1,
            name="Temperature",
            device_id=22222222,  # On sub-device
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Check initial entity
    state = hass.states.get("binary_sensor.kitchen_controller_temperature")
    assert state is not None

    # Get the entity from registry
    entity_entry = entity_registry.async_get(
        "binary_sensor.kitchen_controller_temperature"
    )
    assert entity_entry is not None
    initial_unique_id = entity_entry.unique_id
    # Sub-device entities carry the sub-device id in the unique id
    assert "/22222222/" in initial_unique_id

    # Update entity info - move to main device
    new_entity_info = [
        BinarySensorInfo(
            object_id="temperature",
            key=1,
            name="Temperature",
            device_id=0,  # Now on main device
        ),
    ]

    # Update the entity info
    mock_client.list_entities_services = AsyncMock(return_value=(new_entity_info, []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, new_entity_info, [])
    )

    # Trigger a reconnect
    await device.mock_disconnect(expected_disconnect=False)
    await device.mock_connect()
    await hass.async_block_till_done()

    # The entity_id should remain the same
    state = hass.states.get("binary_sensor.kitchen_controller_temperature")
    assert state is not None

    # Get updated entity from registry
    entity_entry = entity_registry.async_get(
        "binary_sensor.kitchen_controller_temperature"
    )
    assert entity_entry is not None

    # Unique ID device segment should now be the main device id 0
    expected_unique_id = initial_unique_id.replace("/22222222/", "/0/")
    assert entity_entry.unique_id == expected_unique_id

    # Entity should now be associated with the main device
    main_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address),
        device.entry.entry_id,
    )
    assert main_device is not None
    assert entity_entry.device_id == main_device.id


async def test_unique_id_migration_between_sub_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test that unique_id is migrated when entity moves between sub-devices."""
    # Initial setup: two sub-devices
    sub_devices = [
        SubDeviceInfo(device_id=22222222, name="kitchen_controller", area_id=0),
        SubDeviceInfo(device_id=33333333, name="bedroom_controller", area_id=0),
    ]

    device_info = {
        "name": "test",
        "devices": sub_devices,
    }

    # Entity on first sub-device
    entity_info = [
        BinarySensorInfo(
            object_id="temperature",
            key=1,
            name="Temperature",
            device_id=22222222,  # On kitchen_controller
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Check initial entity
    state = hass.states.get("binary_sensor.kitchen_controller_temperature")
    assert state is not None

    # Get the entity from registry
    entity_entry = entity_registry.async_get(
        "binary_sensor.kitchen_controller_temperature"
    )
    assert entity_entry is not None
    initial_unique_id = entity_entry.unique_id
    # Sub-device entities carry the sub-device id in the unique id
    assert "/22222222/" in initial_unique_id

    # Update entity info - move to second sub-device
    new_entity_info = [
        BinarySensorInfo(
            object_id="temperature",
            key=1,
            name="Temperature",
            device_id=33333333,  # Now on bedroom_controller
        ),
    ]

    # Update the entity info
    mock_client.list_entities_services = AsyncMock(return_value=(new_entity_info, []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(device.device_info, new_entity_info, [])
    )

    # Trigger a reconnect
    await device.mock_disconnect(expected_disconnect=False)
    await device.mock_connect()
    await hass.async_block_till_done()

    # The entity_id should remain the same
    state = hass.states.get("binary_sensor.kitchen_controller_temperature")
    assert state is not None

    # Get updated entity from registry
    entity_entry = entity_registry.async_get(
        "binary_sensor.kitchen_controller_temperature"
    )
    assert entity_entry is not None

    # Unique ID device segment should have moved from 22222222 to 33333333
    expected_unique_id = initial_unique_id.replace("/22222222/", "/33333333/")
    assert entity_entry.unique_id == expected_unique_id

    # Entity should now be associated with the second sub-device
    bedroom_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_33333333"), device.entry.entry_id
    )
    assert bedroom_device is not None
    assert entity_entry.device_id == bedroom_device.id


async def test_entity_device_id_rename_in_yaml(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entities re-added when user renames device_id in YAML."""
    # Initial setup: entity on sub-device with device_id 11111111
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="old_device", area_id=0),
    ]

    device_info = {
        "name": "test",
        "devices": sub_devices,
    }

    # Entity on sub-device
    entity_info = [
        BinarySensorInfo(
            object_id="sensor",
            key=1,
            name="Sensor",
            device_id=11111111,
        ),
    ]

    states = [
        BinarySensorState(key=1, state=True, missing_state=False, device_id=11111111),
    ]

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Verify initial entity setup
    state = hass.states.get("binary_sensor.old_device_sensor")
    assert state is not None
    assert state.state == STATE_ON

    # Wait for entity to be registered
    await hass.async_block_till_done()

    # Get the entity from registry
    entity_entry = entity_registry.async_get("binary_sensor.old_device_sensor")
    assert entity_entry is not None
    initial_unique_id = entity_entry.unique_id
    # Sub-device entities carry the sub-device id in the unique id
    assert "/11111111/" in initial_unique_id

    # Simulate user renaming device_id in YAML config
    # The device_id hash changes from 11111111 to 99999999
    # This is treated as a completely new device
    renamed_sub_devices = [
        SubDeviceInfo(device_id=99999999, name="renamed_device", area_id=0),
    ]

    # Get the config entry from hass
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    # Update device_id_to_name mapping
    entry_data = entry.runtime_data
    entry_data.device_id_to_name = {
        sub_device.device_id: sub_device.name for sub_device in renamed_sub_devices
    }

    # Create new DeviceInfo with renamed device
    current_device_info = mock_client.device_info.return_value
    device_info_dict = asdict(current_device_info)
    device_info_dict["devices"] = renamed_sub_devices
    new_device_info = DeviceInfo(**device_info_dict)
    mock_client.device_info.return_value = new_device_info

    # Entity info now has the new device_id
    new_entity_info = [
        BinarySensorInfo(
            object_id="sensor",  # Same object_id
            key=1,  # Same key
            name="Sensor",
            device_id=99999999,  # New device_id after rename
        ),
    ]

    # Update the entity info
    mock_client.list_entities_services = AsyncMock(return_value=(new_entity_info, []))
    mock_client.device_info_and_list_entities = AsyncMock(
        return_value=(new_device_info, new_entity_info, [])
    )

    # Trigger a reconnect to simulate the YAML config change
    await device.mock_disconnect(expected_disconnect=False)
    await device.mock_connect()
    await hass.async_block_till_done()

    # The old entity should be gone (device was deleted)
    state = hass.states.get("binary_sensor.old_device_sensor")
    assert state is None

    # A new entity should exist with a new entity_id based on the new device name
    # This is a completely new entity, not a migrated one
    state = hass.states.get("binary_sensor.renamed_device_sensor")
    assert state is not None
    assert state.state == STATE_ON

    # Get the new entity from registry
    entity_entry = entity_registry.async_get("binary_sensor.renamed_device_sensor")
    assert entity_entry is not None

    # Unique ID device segment should have the new device_id
    expected_unique_id = initial_unique_id.replace("/11111111/", "/99999999/")
    assert entity_entry.unique_id == expected_unique_id

    # Entity should be associated with the new device
    renamed_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_99999999"), device.entry.entry_id
    )
    assert renamed_device is not None
    assert entity_entry.device_id == renamed_device.id


_MOVE_SUB_DEVICES = [
    SubDeviceInfo(device_id=11111111, name="Sub Device 1", area_id=0),
    SubDeviceInfo(device_id=22222222, name="Sub Device 2", area_id=0),
]
_MOVE_INITIAL_INFOS = [
    BinarySensorInfo(object_id="a", key=1, name="A", device_id=11111111),
    BinarySensorInfo(object_id="b", key=1, name="B", device_id=22222222),
]
_MOVE_INITIAL_STATES = [
    BinarySensorState(key=1, state=True, missing_state=False, device_id=11111111),
    BinarySensorState(key=1, state=False, missing_state=False, device_id=22222222),
]


@pytest.mark.parametrize(
    ("new_infos", "expected_states"),
    [
        pytest.param(
            [
                BinarySensorInfo(object_id="a", key=1, name="A", device_id=22222222),
                BinarySensorInfo(object_id="b", key=1, name="B", device_id=11111111),
            ],
            [STATE_ON, STATE_OFF],
            id="swap_sub_devices_same_key",
        ),
        pytest.param(
            [BinarySensorInfo(object_id="a", key=5, name="A", device_id=22222222)],
            [STATE_UNKNOWN],
            id="move_with_new_key_drops_state",
        ),
        pytest.param(
            [BinarySensorInfo(object_id="a", key=1, name="A", device_id=22222222)],
            [STATE_ON],
            id="move_onto_removed_entity_slot_keeps_own_state",
        ),
    ],
)
async def test_entity_move_between_devices_carries_cached_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    new_infos: list[BinarySensorInfo],
    expected_states: list[str],
) -> None:
    """Test an entity that moves between devices keeps only its own cached state."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"name": "test", "devices": _MOVE_SUB_DEVICES},
        entity_info=_MOVE_INITIAL_INFOS,
        states=_MOVE_INITIAL_STATES,
    )
    mac = device.device_info.mac_address

    def _assert_states(infos: list[BinarySensorInfo], expected: list[str]) -> None:
        for info, expected_state in zip(infos, expected, strict=True):
            entity_id = entity_registry.async_get_entity_id(
                Platform.BINARY_SENSOR, DOMAIN, build_device_unique_id(mac, info)
            )
            assert entity_id is not None
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == expected_state

    _assert_states(_MOVE_INITIAL_INFOS, [STATE_ON, STATE_OFF])

    # No states are replayed on connect so only the carried state is observable
    await reconnect_with_updated_entity_info(hass, device, new_infos, states=[])

    _assert_states(new_infos, expected_states)


@pytest.mark.parametrize(
    ("unicode_name", "expected_entity_id"),
    [
        ("Árvíztűrő tükörfúrógép", "binary_sensor.test_arvizturo_tukorfurogep"),
        ("Teplota venku °C", "binary_sensor.test_teplota_venku_degc"),
        ("Влажность %", "binary_sensor.test_vlazhnost"),
        ("中文传感器", "binary_sensor.test_zhong_wen_chuan_gan_qi"),
        ("Sensor à côté", "binary_sensor.test_sensor_a_cote"),
        ("τιμή αισθητήρα", "binary_sensor.test_time_aisthetera"),
    ],
)
async def test_entity_with_unicode_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
    unicode_name: str,
    expected_entity_id: str,
) -> None:
    """Test that entities with Unicode names get proper entity IDs.

    This verifies the fix for Unicode entity names where ESPHome's C++ code
    sanitizes Unicode characters to underscores (not UTF-8 aware), but the
    entity_id should use the original name from entity_info.name rather than
    the sanitized object_id to preserve Unicode characters properly.
    """
    # Simulate what ESPHome would send - a heavily sanitized object_id
    # but with the original Unicode name preserved
    sanitized_object_id = "_".join("_" * len(word) for word in unicode_name.split())

    entity_info = [
        BinarySensorInfo(
            object_id=sanitized_object_id,  # ESPHome sends the sanitized version
            key=1,
            name=unicode_name,  # But also sends the original Unicode name,
        )
    ]
    states = [BinarySensorState(key=1, state=True)]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    # The entity_id should be based on the Unicode name, properly transliterated
    state = hass.states.get(expected_entity_id)
    assert state is not None, f"Entity with ID {expected_entity_id} should exist"
    assert state.state == STATE_ON

    # The friendly name should preserve the original Unicode characters
    assert state.attributes["friendly_name"] == f"Test {unicode_name}"

    # Verify that using the sanitized object_id would NOT find the entity
    # This confirms we're not using the object_id for entity_id generation
    wrong_entity_id = f"binary_sensor.test_{sanitized_object_id}"
    wrong_state = hass.states.get(wrong_entity_id)
    assert wrong_state is None, f"Entity should NOT be found at {wrong_entity_id}"


async def test_entity_without_name_uses_device_name_only(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test that entities without a name fall back to using device name only.

    When entity_info.name is empty, the entity_id should just be domain.device_name
    without the object_id appended, as noted in the comment in entity.py.
    """
    entity_info = [
        BinarySensorInfo(
            object_id="some_sanitized_id",
            key=1,
            name="",  # Empty name,
        )
    ]
    states = [BinarySensorState(key=1, state=True)]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    # With empty name, entity_id should just be domain.device_name
    expected_entity_id = "binary_sensor.test"
    state = hass.states.get(expected_entity_id)
    assert state is not None, f"Entity {expected_entity_id} should exist"
    assert state.state == STATE_ON


async def test_entities_rekeyed_after_firmware_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entities survive the key changing when the name stays the same.

    The API key is only stable for a session; a firmware update may
    re-derive every key. The registry entries must be preserved so
    helpers pointing at the entities are not deleted.
    """
    entity_info, states = _two_binary_sensor_setup()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    assert hass.states.get("binary_sensor.test_sensor_one").state == STATE_ON
    assert hass.states.get("binary_sensor.test_sensor_two").state == STATE_ON

    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    entry_two = entity_registry.async_get("binary_sensor.test_sensor_two")
    assert entry_one is not None
    assert entry_two is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.test_sensor_two")

    # Firmware update re-derives every key, names unchanged
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=101,
            name="Sensor One",
        ),
        BinarySensorInfo(
            object_id="sensor_two",
            key=102,
            name="Sensor Two",
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass,
        device,
        updated_entity_info,
        states=[
            BinarySensorState(key=101, state=True, missing_state=False),
            BinarySensorState(key=102, state=True, missing_state=False),
        ],
    )

    new_entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    new_entry_two = entity_registry.async_get("binary_sensor.test_sensor_two")
    assert new_entry_one is not None
    assert new_entry_two is not None
    assert new_entry_one.id == entry_one.id
    assert new_entry_two.id == entry_two.id
    assert new_entry_one.unique_id == entry_one.unique_id
    assert new_entry_two.unique_id == entry_two.unique_id
    assert actions_one == []
    assert actions_two == []

    # State updates must follow the new key
    device.set_state(BinarySensorState(key=101, state=False, missing_state=False))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_sensor_one").state == STATE_OFF

    # The old key must be ignored
    device.set_state(BinarySensorState(key=1, state=True, missing_state=False))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_sensor_one").state == STATE_OFF

    # Reconnect again with stable keys, static info updates must
    # reach the entity under the new key
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=101,
            name="Sensor One",
            icon="mdi:motion-sensor",
        ),
        BinarySensorInfo(
            object_id="sensor_two",
            key=102,
            name="Sensor Two",
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    device.set_state(BinarySensorState(key=101, state=True, missing_state=False))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_sensor_one")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ICON] == "mdi:motion-sensor"
    assert actions_one == []
    assert actions_two == []


async def test_entities_rekeyed_after_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entities restored from storage survive a key change on connect.

    Covers the path where entities are created from stored static infos
    with the old keys and the first connect delivers the new keys.
    """
    entity_info, states = _two_binary_sensor_setup()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    entry = device.entry
    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    entry_two = entity_registry.async_get("binary_sensor.test_sensor_two")
    assert entry_one is not None
    assert entry_two is not None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.test_sensor_two")

    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=101,
            name="Sensor One",
        ),
        BinarySensorInfo(
            object_id="sensor_two",
            key=102,
            name="Sensor Two",
        ),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=updated_entity_info,
        entry=entry,
    )
    await hass.async_block_till_done()

    new_entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    new_entry_two = entity_registry.async_get("binary_sensor.test_sensor_two")
    assert new_entry_one is not None
    assert new_entry_two is not None
    assert new_entry_one.id == entry_one.id
    assert new_entry_two.id == entry_two.id
    assert "remove" not in actions_one
    assert "remove" not in actions_two

    device.set_state(BinarySensorState(key=101, state=True, missing_state=False))
    device.set_state(BinarySensorState(key=102, state=False, missing_state=False))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_sensor_one").state == STATE_ON
    assert hass.states.get("binary_sensor.test_sensor_two").state == STATE_OFF


async def test_entity_rekeyed_and_another_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a key change combined with a genuine entity removal."""
    entity_info, states = _two_binary_sensor_setup()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert entry_one is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.test_sensor_two")

    # Sensor One is re-keyed, Sensor Two is gone from the config
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=101,
            name="Sensor One",
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass,
        device,
        updated_entity_info,
        states=[BinarySensorState(key=101, state=True, missing_state=False)],
    )

    new_entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert new_entry_one is not None
    assert new_entry_one.id == entry_one.id
    assert actions_one == []

    assert entity_registry.async_get("binary_sensor.test_sensor_two") is None
    assert actions_two == ["remove"]


async def test_entity_rekeyed_to_another_entities_old_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a re-key that collides with an unrelated entity's old key.

    Sensor One takes over the key that used to belong to Sensor Two,
    which is removed at the same time. The unique_id match must win so
    the entities do not swap identities.
    """
    entity_info, states = _two_binary_sensor_setup()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert entry_one is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.test_sensor_two")

    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=2,
            name="Sensor One",
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert new_entry_one is not None
    assert new_entry_one.id == entry_one.id
    assert new_entry_one.unique_id == entry_one.unique_id
    assert actions_one == []

    assert entity_registry.async_get("binary_sensor.test_sensor_two") is None
    assert actions_two == ["remove"]

    # Sensor One must follow its new key and keep its own identity
    device.set_state(BinarySensorState(key=2, state=False, missing_state=False))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_sensor_one")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Test Sensor One"


async def test_entity_renamed_with_stable_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a rename that keeps the object_id and key stable.

    A case only rename keeps the object_id, and therefore the key,
    stable; the entity is updated in place and its registry entry
    follows the new name based unique_id.
    """
    entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=1,
            name="Sensor One",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert entry_one is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")

    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=1,
            name="SENSOR ONE",
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert new_entry_one is not None
    assert new_entry_one.id == entry_one.id
    assert "remove" not in actions_one
    # The registry unique_id must follow the rename so the entry is
    # not orphaned on the next restart
    assert new_entry_one.unique_id == build_device_unique_id(
        device.device_info.mac_address, updated_entity_info[0]
    )

    device.set_state(BinarySensorState(key=1, state=False, missing_state=False))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_sensor_one")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Test SENSOR ONE"


async def test_entity_renamed_and_rekeyed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a rename on firmware where the key is derived from the name.

    Both the name and the key change so this is treated as a new entity.
    """
    entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=1,
            name="Sensor One",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    assert entity_registry.async_get("binary_sensor.test_sensor_one") is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")

    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one_renamed",
            key=101,
            name="Sensor One Renamed",
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    assert entity_registry.async_get("binary_sensor.test_sensor_one") is None
    assert actions_one == ["remove"]
    assert (
        entity_registry.async_get("binary_sensor.test_sensor_one_renamed") is not None
    )

    device.set_state(BinarySensorState(key=101, state=False, missing_state=False))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_sensor_one_renamed").state == STATE_OFF


async def test_entities_rekeyed_on_sub_devices_with_same_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test re-keying entities with the same name on different sub devices."""
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
        SubDeviceInfo(device_id=22222222, name="sub_two", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=11111111,
        ),
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=22222222,
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False, device_id=11111111),
        BinarySensorState(key=1, state=True, missing_state=False, device_id=22222222),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.sub_one_battery")
    entry_two = entity_registry.async_get("binary_sensor.sub_two_battery")
    assert entry_one is not None
    assert entry_two is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.sub_one_battery")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.sub_two_battery")

    updated_entity_info = [
        BinarySensorInfo(
            object_id="battery",
            key=101,
            name="Battery",
            device_id=11111111,
        ),
        BinarySensorInfo(
            object_id="battery",
            key=101,
            name="Battery",
            device_id=22222222,
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_one = entity_registry.async_get("binary_sensor.sub_one_battery")
    new_entry_two = entity_registry.async_get("binary_sensor.sub_two_battery")
    assert new_entry_one is not None
    assert new_entry_two is not None
    assert new_entry_one.id == entry_one.id
    assert new_entry_two.id == entry_two.id
    assert actions_one == []
    assert actions_two == []

    # Each entity must follow the new key on its own device
    device.set_state(
        BinarySensorState(key=101, state=False, missing_state=False, device_id=11111111)
    )
    device.set_state(
        BinarySensorState(key=101, state=True, missing_state=False, device_id=22222222)
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.sub_one_battery").state == STATE_OFF
    assert hass.states.get("binary_sensor.sub_two_battery").state == STATE_ON


async def test_entities_swap_keys(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test two entities swapping keys in the same update.

    Keys are not collision safe; a firmware update may hand one
    entity's old key to another entity. Each entity must follow its
    own unique_id and never adopt the other's identity.
    """
    entity_info, states = _two_binary_sensor_setup()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    entry_two = entity_registry.async_get("binary_sensor.test_sensor_two")
    assert entry_one is not None
    assert entry_two is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.test_sensor_two")

    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=2,
            name="Sensor One",
        ),
        BinarySensorInfo(
            object_id="sensor_two",
            key=1,
            name="Sensor Two",
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    new_entry_two = entity_registry.async_get("binary_sensor.test_sensor_two")
    assert new_entry_one is not None
    assert new_entry_two is not None
    assert new_entry_one.id == entry_one.id
    assert new_entry_two.id == entry_two.id
    assert new_entry_one.unique_id == entry_one.unique_id
    assert new_entry_two.unique_id == entry_two.unique_id
    assert actions_one == []
    assert actions_two == []

    # Each entity must follow its swapped key with its own identity
    device.set_state(BinarySensorState(key=2, state=False, missing_state=False))
    device.set_state(BinarySensorState(key=1, state=True, missing_state=False))
    await hass.async_block_till_done()
    state_one = hass.states.get("binary_sensor.test_sensor_one")
    state_two = hass.states.get("binary_sensor.test_sensor_two")
    assert state_one.state == STATE_OFF
    assert state_two.state == STATE_ON
    assert state_one.attributes[ATTR_FRIENDLY_NAME] == "Test Sensor One"
    assert state_two.attributes[ATTR_FRIENDLY_NAME] == "Test Sensor Two"


async def test_entity_rekeyed_and_moved_between_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test an entity changing key and device in the same update.

    The name is the device independent identity, so the entity is
    migrated to the new device instead of being removed and recreated.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=1,
            name="Sensor One",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert entry_one is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")

    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=101,
            name="Sensor One",
            device_id=11111111,
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert new_entry is not None
    assert new_entry.id == entry_one.id
    assert "remove" not in actions_one

    sub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_11111111"), device.entry.entry_id
    )
    assert sub_device is not None
    assert new_entry.device_id == sub_device.id

    device.set_state(
        BinarySensorState(key=101, state=False, missing_state=False, device_id=11111111)
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_sensor_one").state == STATE_OFF


async def test_entity_new_key_reuses_removed_entity_key_on_other_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a new entity reusing a removed entity's key on another device.

    The names differ, so the new entity must not steal the removed
    entity's registry entry through the cross device key match.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=1,
            name="Sensor One",
        ),
        BinarySensorInfo(
            object_id="sensor_two",
            key=2,
            name="Sensor Two",
            device_id=11111111,
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False, device_id=11111111),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_two = entity_registry.async_get("binary_sensor.sub_one_sensor_two")
    assert entry_two is not None

    actions_two = track_entity_registry_actions(
        hass, "binary_sensor.sub_one_sensor_two"
    )

    # Sensor Two is removed while a new Sensor Three on the main
    # device reuses its key
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=1,
            name="Sensor One",
        ),
        BinarySensorInfo(
            object_id="sensor_three",
            key=2,
            name="Sensor Three",
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    assert entity_registry.async_get("binary_sensor.sub_one_sensor_two") is None
    assert actions_two == ["remove"]
    entry_three = entity_registry.async_get("binary_sensor.test_sensor_three")
    assert entry_three is not None
    assert entry_three.id != entry_two.id

    device.set_state(BinarySensorState(key=2, state=False, missing_state=False))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_sensor_three").state == STATE_OFF


async def test_entities_with_same_name_moved_between_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test same named entities moving between devices at the same time.

    The name is ambiguous so the moves are resolved by the key, which
    migrates each entity to its own new device.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
        SubDeviceInfo(device_id=22222222, name="sub_two", area_id=0),
        SubDeviceInfo(device_id=33333333, name="sub_three", area_id=0),
        SubDeviceInfo(device_id=44444444, name="sub_four", area_id=0),
        SubDeviceInfo(device_id=55555555, name="sub_five", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=11111111,
        ),
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=22222222,
        ),
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=55555555,
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False, device_id=11111111),
        BinarySensorState(key=1, state=True, missing_state=False, device_id=22222222),
        BinarySensorState(key=1, state=True, missing_state=False, device_id=55555555),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.sub_one_battery")
    entry_two = entity_registry.async_get("binary_sensor.sub_two_battery")
    assert entry_one is not None
    assert entry_two is not None
    assert entity_registry.async_get("binary_sensor.sub_five_battery") is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.sub_one_battery")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.sub_two_battery")
    actions_five = track_entity_registry_actions(hass, "binary_sensor.sub_five_battery")

    # Two of the same named entities move to new sub devices with
    # stable keys while the third is removed
    updated_entity_info = [
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=33333333,
        ),
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=44444444,
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_one = entity_registry.async_get("binary_sensor.sub_one_battery")
    new_entry_two = entity_registry.async_get("binary_sensor.sub_two_battery")
    assert new_entry_one is not None
    assert new_entry_two is not None
    assert new_entry_one.id == entry_one.id
    assert new_entry_two.id == entry_two.id
    assert "remove" not in actions_one
    assert "remove" not in actions_two
    assert entity_registry.async_get("binary_sensor.sub_five_battery") is None
    assert actions_five == ["remove"]

    mac = device.device_info.mac_address
    sub_three = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mac}_33333333"), device.entry.entry_id
    )
    sub_four = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mac}_44444444"), device.entry.entry_id
    )
    assert sub_three is not None
    assert sub_four is not None
    assert new_entry_one.device_id == sub_three.id
    assert new_entry_two.device_id == sub_four.id

    # Each entity must follow the key on its new device
    device.set_state(
        BinarySensorState(key=1, state=False, missing_state=False, device_id=33333333)
    )
    device.set_state(
        BinarySensorState(key=1, state=True, missing_state=False, device_id=44444444)
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.sub_one_battery").state == STATE_OFF
    assert hass.states.get("binary_sensor.sub_two_battery").state == STATE_ON


async def test_entity_rekeyed_while_old_key_reused_by_renamed_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a re-key where the freed key is reused by a renamed entity.

    The renamed entity arrives first in the info list and matches
    Sensor Two's old key, but Sensor Two's identity is claimed by a
    later info, so the in place key match must not consume it.
    """
    entity_info, states = _two_binary_sensor_setup()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    entry_two = entity_registry.async_get("binary_sensor.test_sensor_two")
    assert entry_one is not None
    assert entry_two is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.test_sensor_two")

    # Sensor Two is re-keyed 2 to 1 while a renamed entity takes over
    # key 2; the renamed entity is listed first
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_renamed",
            key=2,
            name="Sensor Renamed",
        ),
        BinarySensorInfo(
            object_id="sensor_two",
            key=1,
            name="Sensor Two",
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_two = entity_registry.async_get("binary_sensor.test_sensor_two")
    assert new_entry_two is not None
    assert new_entry_two.id == entry_two.id
    assert new_entry_two.unique_id == entry_two.unique_id
    assert actions_two == []

    # Sensor One is gone and the renamed entity is brand new
    assert entity_registry.async_get("binary_sensor.test_sensor_one") is None
    assert actions_one == ["remove"]
    entry_renamed = entity_registry.async_get("binary_sensor.test_sensor_renamed")
    assert entry_renamed is not None
    assert entry_renamed.id != entry_one.id

    # Each entity must follow its own key with its own identity
    device.set_state(BinarySensorState(key=1, state=False, missing_state=False))
    device.set_state(BinarySensorState(key=2, state=True, missing_state=False))
    await hass.async_block_till_done()
    state_two = hass.states.get("binary_sensor.test_sensor_two")
    state_renamed = hass.states.get("binary_sensor.test_sensor_renamed")
    assert state_two.state == STATE_OFF
    assert state_two.attributes[ATTR_FRIENDLY_NAME] == "Test Sensor Two"
    assert state_renamed.state == STATE_ON


async def test_entity_moved_into_removed_entities_key_slot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device move into a key slot vacated by a removed entity.

    The moved entity keeps its key and lands on the removed entity's
    old (device_id, key) slot; the name match must win so the move is
    migrated instead of being mistaken for a rename of the removed
    entity.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
        SubDeviceInfo(device_id=22222222, name="sub_two", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="batt",
            key=5,
            name="Batt",
            device_id=11111111,
        ),
        BinarySensorInfo(
            object_id="volt",
            key=5,
            name="Volt",
            device_id=22222222,
        ),
    ]
    states = [
        BinarySensorState(key=5, state=True, missing_state=False, device_id=11111111),
        BinarySensorState(key=5, state=True, missing_state=False, device_id=22222222),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_batt = entity_registry.async_get("binary_sensor.sub_one_batt")
    entry_volt = entity_registry.async_get("binary_sensor.sub_two_volt")
    assert entry_batt is not None
    assert entry_volt is not None

    actions_batt = track_entity_registry_actions(hass, "binary_sensor.sub_one_batt")
    actions_volt = track_entity_registry_actions(hass, "binary_sensor.sub_two_volt")

    # Batt moves to sub_two keeping key 5, taking over Volt's old
    # (device_id, key) slot; Volt is removed
    updated_entity_info = [
        BinarySensorInfo(
            object_id="batt",
            key=5,
            name="Batt",
            device_id=22222222,
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_batt = entity_registry.async_get("binary_sensor.sub_one_batt")
    assert new_entry_batt is not None
    assert new_entry_batt.id == entry_batt.id
    assert "remove" not in actions_batt

    sub_two = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_22222222"), device.entry.entry_id
    )
    assert sub_two is not None
    assert new_entry_batt.device_id == sub_two.id

    assert entity_registry.async_get("binary_sensor.sub_two_volt") is None
    assert actions_volt == ["remove"]

    device.set_state(
        BinarySensorState(key=5, state=False, missing_state=False, device_id=22222222)
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.sub_one_batt")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "sub_two Batt"


async def test_entity_moved_while_new_entity_takes_old_slot_listed_first(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a move where a new entity takes the old slot and is listed first.

    The new entity arrives first and matches the mover's old
    (device_id, key) slot, but the mover's name is claimed by a later
    info, so the in place key match must not consume it.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="foo",
            key=1,
            name="Foo",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_foo = entity_registry.async_get("binary_sensor.test_foo")
    assert entry_foo is not None

    actions_foo = track_entity_registry_actions(hass, "binary_sensor.test_foo")

    # Foo moves to the sub device with a new key while new entity Bar
    # takes over Foo's old (device_id, key) slot and is listed first
    updated_entity_info = [
        BinarySensorInfo(
            object_id="bar",
            key=1,
            name="Bar",
        ),
        BinarySensorInfo(
            object_id="foo",
            key=9,
            name="Foo",
            device_id=11111111,
        ),
    ]
    with caplog.at_level(logging.DEBUG, "homeassistant.components.esphome"):
        await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    # Every candidate slot was occupied, so the ambiguous fallback ran
    assert "Ambiguous move for Foo" in caplog.text
    new_entry_foo = entity_registry.async_get("binary_sensor.test_foo")
    assert new_entry_foo is not None
    assert new_entry_foo.id == entry_foo.id
    assert "remove" not in actions_foo

    sub_one = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_11111111"), device.entry.entry_id
    )
    assert sub_one is not None
    assert new_entry_foo.device_id == sub_one.id

    entry_bar = entity_registry.async_get("binary_sensor.test_bar")
    assert entry_bar is not None
    assert entry_bar.id != entry_foo.id

    # Each entity must follow its own key
    device.set_state(
        BinarySensorState(key=9, state=False, missing_state=False, device_id=11111111)
    )
    device.set_state(BinarySensorState(key=1, state=True, missing_state=False))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_foo").state == STATE_OFF
    assert hass.states.get("binary_sensor.test_bar").state == STATE_ON


async def test_entity_renamed_with_stable_key_and_same_named_sibling(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a stable key rename while a sibling device shares the old name.

    The sibling's Battery is claimed by its own unique_id match, so it
    must not block the rename from being matched in place.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
        SubDeviceInfo(device_id=22222222, name="sub_two", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=11111111,
        ),
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=22222222,
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False, device_id=11111111),
        BinarySensorState(key=1, state=True, missing_state=False, device_id=22222222),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_one = entity_registry.async_get("binary_sensor.sub_one_battery")
    entry_two = entity_registry.async_get("binary_sensor.sub_two_battery")
    assert entry_one is not None
    assert entry_two is not None

    actions_one = track_entity_registry_actions(hass, "binary_sensor.sub_one_battery")
    actions_two = track_entity_registry_actions(hass, "binary_sensor.sub_two_battery")

    # Case only rename on sub_one keeps the object_id and key stable;
    # sub_two still carries the old name
    updated_entity_info = [
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="BATTERY",
            device_id=11111111,
        ),
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=22222222,
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_one = entity_registry.async_get("binary_sensor.sub_one_battery")
    new_entry_two = entity_registry.async_get("binary_sensor.sub_two_battery")
    assert new_entry_one is not None
    assert new_entry_two is not None
    assert new_entry_one.id == entry_one.id
    assert new_entry_two.id == entry_two.id
    assert actions_two == []
    assert "remove" not in actions_one
    # The renamed entity's registry entry follows the new unique_id
    assert new_entry_one.unique_id == build_device_unique_id(
        device.device_info.mac_address, updated_entity_info[0]
    )

    device.set_state(
        BinarySensorState(key=1, state=False, missing_state=False, device_id=11111111)
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.sub_one_battery")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "sub_one BATTERY"


async def test_disabled_entity_rekeyed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a key change for a disabled entity.

    A disabled entity has no live object and no key subscriptions, so
    the key change has no subscriber; the registry entry must still be
    preserved.
    """
    entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=1,
            name="Sensor One",
            disabled_by_default=True,
        ),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
    )
    entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert entry_one is not None
    assert entry_one.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    actions_one = track_entity_registry_actions(hass, "binary_sensor.test_sensor_one")

    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=101,
            name="Sensor One",
            disabled_by_default=True,
        ),
    ]
    with caplog.at_level(logging.DEBUG, "homeassistant.components.esphome"):
        await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    assert "no subscriber for key change 1 -> 101" in caplog.text
    new_entry_one = entity_registry.async_get("binary_sensor.test_sensor_one")
    assert new_entry_one is not None
    assert new_entry_one.id == entry_one.id
    assert actions_one == []


async def test_entity_renamed_while_same_named_sibling_moves(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a stable key rename while a same named sibling moves devices.

    The mover must claim the sibling on sub_one, not the rename
    candidate on the main device, and both registry entries must be
    preserved.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
        SubDeviceInfo(device_id=22222222, name="sub_two", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
        ),
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=11111111,
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=1, state=True, missing_state=False, device_id=11111111),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_main = entity_registry.async_get("binary_sensor.test_battery")
    entry_sub = entity_registry.async_get("binary_sensor.sub_one_battery")
    assert entry_main is not None
    assert entry_sub is not None

    actions_main = track_entity_registry_actions(hass, "binary_sensor.test_battery")
    actions_sub = track_entity_registry_actions(hass, "binary_sensor.sub_one_battery")

    # Case only rename on the main device while the sub_one sibling
    # moves to sub_two; the renamed entity is listed first
    updated_entity_info = [
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="BATTERY",
        ),
        BinarySensorInfo(
            object_id="battery",
            key=1,
            name="Battery",
            device_id=22222222,
        ),
    ]
    await reconnect_with_updated_entity_info(hass, device, updated_entity_info)

    new_entry_main = entity_registry.async_get("binary_sensor.test_battery")
    new_entry_sub = entity_registry.async_get("binary_sensor.sub_one_battery")
    assert new_entry_main is not None
    assert new_entry_sub is not None
    assert new_entry_main.id == entry_main.id
    assert new_entry_sub.id == entry_sub.id
    assert "remove" not in actions_main
    assert "remove" not in actions_sub

    # The rename followed the new unique_id and stayed on the main device
    assert new_entry_main.unique_id == build_device_unique_id(
        device.device_info.mac_address, updated_entity_info[0]
    )
    # The sibling migrated to sub_two
    sub_two = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_22222222"), device.entry.entry_id
    )
    assert sub_two is not None
    assert new_entry_sub.device_id == sub_two.id

    device.set_state(BinarySensorState(key=1, state=False, missing_state=False))
    device.set_state(
        BinarySensorState(key=1, state=True, missing_state=False, device_id=22222222)
    )
    await hass.async_block_till_done()
    state_main = hass.states.get("binary_sensor.test_battery")
    state_sub = hass.states.get("binary_sensor.sub_one_battery")
    assert state_main.state == STATE_OFF
    assert state_main.attributes[ATTR_FRIENDLY_NAME] == "Test BATTERY"
    assert state_sub.state == STATE_ON


async def test_new_entities_reusing_retired_keys_do_not_adopt_stale_states(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test new entities reusing retired keys start unknown.

    Keys retired by a re-key or a removal may be handed to unrelated
    entities by a later firmware build; those entities must come up
    unknown instead of adopting the retired key's last state.
    """
    entity_info, states = _two_binary_sensor_setup()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    assert hass.states.get("binary_sensor.test_sensor_one").state == STATE_ON
    assert hass.states.get("binary_sensor.test_sensor_two").state == STATE_ON

    # Sensor One is re-keyed to 101, Sensor Two is removed
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=101,
            name="Sensor One",
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass,
        device,
        updated_entity_info,
        states=[BinarySensorState(key=101, state=True, missing_state=False)],
    )
    assert hass.states.get("binary_sensor.test_sensor_two") is None

    # A later build hands the retired keys 1 and 2 to new entities;
    # no states are streamed for them
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=101,
            name="Sensor One",
        ),
        BinarySensorInfo(
            object_id="sensor_three",
            key=1,
            name="Sensor Three",
        ),
        BinarySensorInfo(
            object_id="sensor_four",
            key=2,
            name="Sensor Four",
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass, device, updated_entity_info, states=[]
    )

    assert hass.states.get("binary_sensor.test_sensor_three").state == STATE_UNKNOWN
    assert hass.states.get("binary_sensor.test_sensor_four").state == STATE_UNKNOWN


async def test_new_entity_on_other_device_reusing_removed_entities_key(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a new entity on another device reusing a removed entity's key.

    The key stays live on the other device, so the removed entity's
    cached state must be dropped by slot, not by key, or the new
    entity would adopt it.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="volt",
            key=2,
            name="Volt",
        ),
    ]
    states = [
        BinarySensorState(key=2, state=True, missing_state=False),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    assert hass.states.get("binary_sensor.test_volt").state == STATE_ON

    # Volt is removed while a new Batt on sub_one reuses key 2;
    # no state is streamed for Batt
    updated_entity_info = [
        BinarySensorInfo(
            object_id="batt",
            key=2,
            name="Batt",
            device_id=11111111,
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass, device, updated_entity_info, states=[]
    )

    assert hass.states.get("binary_sensor.test_volt") is None
    assert hass.states.get("binary_sensor.sub_one_batt").state == STATE_UNKNOWN


async def test_unnamed_entities_do_not_pair_across_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test unnamed entities are not matched as moves across devices.

    An unnamed entity's identity is its device derived object_id, so a
    removed unnamed entity must not hand its registry entry to an
    unrelated unnamed entity appearing on another device.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="test",
            key=1,
            name="",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    entry_main = entity_registry.async_get("binary_sensor.test")
    assert entry_main is not None

    actions_main = track_entity_registry_actions(hass, "binary_sensor.test")

    # The main device's unnamed entity is removed while an unrelated
    # unnamed entity appears on sub_one
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sub_one",
            key=2,
            name="",
            device_id=11111111,
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass, device, updated_entity_info, states=[]
    )

    assert entity_registry.async_get("binary_sensor.test") is None
    assert actions_main == ["remove"]
    entry_sub = entity_registry.async_get("binary_sensor.sub_one")
    assert entry_sub is not None
    assert entry_sub.id != entry_main.id


async def test_moved_entity_does_not_adopt_removed_entities_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a mover landing on a removed entity's key starts unknown.

    The removed entity's cached state sits under the mover's new key
    and must be dropped, or the re-added mover would adopt it.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="foo",
            key=5,
            name="Foo",
        ),
        BinarySensorInfo(
            object_id="bar",
            key=9,
            name="Bar",
            device_id=11111111,
        ),
    ]
    states = [
        BinarySensorState(key=5, state=True, missing_state=False),
        BinarySensorState(key=9, state=False, missing_state=False, device_id=11111111),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    assert hass.states.get("binary_sensor.test_foo").state == STATE_ON
    assert hass.states.get("binary_sensor.sub_one_bar").state == STATE_OFF

    # Foo is removed while Bar moves to the main device and a firmware
    # rebuild hands it Foo's old key; no states are streamed
    updated_entity_info = [
        BinarySensorInfo(
            object_id="bar",
            key=5,
            name="Bar",
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass, device, updated_entity_info, states=[]
    )

    assert hass.states.get("binary_sensor.test_foo") is None
    assert hass.states.get("binary_sensor.sub_one_bar").state == STATE_UNKNOWN


async def test_entity_move_with_claimed_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a device move whose target unique_id is already claimed.

    An orphaned registry entry holding the target unique_id must not
    abort the update; the move keeps its old unique_id and the rest of
    the entities are still processed.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info = [
        BinarySensorInfo(
            object_id="foo",
            key=1,
            name="Foo",
        ),
        BinarySensorInfo(
            object_id="other",
            key=2,
            name="Other",
        ),
    ]
    states = [
        BinarySensorState(key=1, state=True, missing_state=False),
        BinarySensorState(key=2, state=True, missing_state=False),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    assert hass.states.get("binary_sensor.test_foo").state == STATE_ON
    entry_foo = entity_registry.async_get("binary_sensor.test_foo")
    assert entry_foo is not None

    # An orphaned registry entry already claims Foo's post move unique_id
    moved_info = BinarySensorInfo(
        object_id="foo",
        key=1,
        name="Foo",
        device_id=11111111,
    )
    orphan = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        build_device_unique_id(device.device_info.mac_address, moved_info),
        config_entry=device.entry,
    )

    updated_entity_info = [
        moved_info,
        BinarySensorInfo(
            object_id="other",
            key=2,
            name="Other",
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass,
        device,
        updated_entity_info,
        states=[
            BinarySensorState(
                key=1, state=True, missing_state=False, device_id=11111111
            ),
            BinarySensorState(key=2, state=False, missing_state=False),
        ],
    )

    # The update completed: the sibling still processes states
    assert hass.states.get("binary_sensor.test_other").state == STATE_OFF
    # The blocked migration leaves the original entry untouched; the
    # moved entity binds to the orphan
    original = entity_registry.async_get("binary_sensor.test_foo")
    assert original is not None
    assert original.unique_id == entry_foo.unique_id
    assert original.device_id == entry_foo.device_id
    assert hass.states.get("binary_sensor.test_foo").state == STATE_UNAVAILABLE
    assert entity_registry.async_get(orphan.entity_id) is not None
    assert hass.states.get(orphan.entity_id).state == STATE_ON


async def test_mover_does_not_adopt_other_movers_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test two movers from one device cannot adopt each other's state.

    A mover landing on another mover's old key must start unknown; the
    cached state under that key was written from a different slot.
    """
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="sub_one", area_id=0),
        SubDeviceInfo(device_id=22222222, name="sub_two", area_id=0),
    ]
    device_info = {
        "devices": sub_devices,
    }
    entity_info, states = _two_binary_sensor_setup()
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )
    assert hass.states.get("binary_sensor.test_sensor_one").state == STATE_ON
    assert hass.states.get("binary_sensor.test_sensor_two").state == STATE_ON

    # Both entities move to sub devices while a firmware rebuild
    # re-derives keys; Sensor Two lands on Sensor One's old key and
    # no states are streamed
    updated_entity_info = [
        BinarySensorInfo(
            object_id="sensor_one",
            key=5,
            name="Sensor One",
            device_id=11111111,
        ),
        BinarySensorInfo(
            object_id="sensor_two",
            key=1,
            name="Sensor Two",
            device_id=22222222,
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass, device, updated_entity_info, states=[]
    )

    assert hass.states.get("binary_sensor.test_sensor_one").state == STATE_UNKNOWN
    assert hass.states.get("binary_sensor.test_sensor_two").state == STATE_UNKNOWN
