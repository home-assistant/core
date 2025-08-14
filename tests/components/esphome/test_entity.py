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
    SubDeviceInfo,
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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .conftest import (
    MockESPHomeDevice,
    MockESPHomeDeviceType,
    MockGenericDeviceEntryType,
)


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
    """Test entities and their registry entry are removed when static info changes after a reload."""
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
    """Test name and entity_id for a device a friendly name and an entity without a name."""
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
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test entities are assigned to correct sub devices."""
    device_registry = dr.async_get(hass)

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
    main_device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address)}
    )
    assert main_device is not None

    # Check entities are assigned to correct devices
    main_sensor = entity_registry.async_get("binary_sensor.test_main_sensor")
    assert main_sensor is not None
    assert main_sensor.device_id == main_device.id

    # Check sub device 1 entity
    sub_device_1 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_11111111")}
    )
    assert sub_device_1 is not None

    motion_sensor = entity_registry.async_get("binary_sensor.motion_sensor_motion")
    assert motion_sensor is not None
    assert motion_sensor.device_id == sub_device_1.id

    # Check sub device 2 entity
    sub_device_2 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_22222222")}
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
    # Since sub device has empty name, it falls back to main device name "test"
    state_1 = hass.states.get("binary_sensor.test_motion_detected")
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
    state_4 = hass.states.get("binary_sensor.test_main_status")
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
    main_device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address)}
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
    sub_device_1 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_11111111")}
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
    sub_device_2 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_22222222")}
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
    """Test entity_id when sub device has empty name (falls back to main device name)."""
    # Define sub device with empty name
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="", area_id=0),  # Empty name
    ]

    device_info = {
        "devices": sub_devices,
        "name": "main_device",
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


async def test_unique_id_migration_when_entity_moves_between_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test that unique_id is migrated when entity moves between devices while entity_id stays the same."""
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
    # Initial unique_id should not have @device_id suffix since it's on main device
    assert "@" not in initial_unique_id

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

    # The entity_id doesn't change when moving between devices
    # Only the unique_id gets updated with @device_id suffix
    state = hass.states.get("binary_sensor.test_temperature")
    assert state is not None

    # Get updated entity from registry - entity_id should be the same
    entity_entry = entity_registry.async_get("binary_sensor.test_temperature")
    assert entity_entry is not None

    # Unique ID should have been migrated to include @device_id
    # This is done by our build_device_unique_id wrapper
    expected_unique_id = f"{initial_unique_id}@22222222"
    assert entity_entry.unique_id == expected_unique_id

    # Entity should now be associated with the sub-device
    sub_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_22222222")}
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
    """Test that unique_id is migrated when entity moves from sub-device to main device."""
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
    # Initial unique_id should have @device_id suffix since it's on sub-device
    assert "@22222222" in initial_unique_id

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

    # Unique ID should have been migrated to remove @device_id suffix
    expected_unique_id = initial_unique_id.replace("@22222222", "")
    assert entity_entry.unique_id == expected_unique_id

    # Entity should now be associated with the main device
    main_device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device.device_info.mac_address)}
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
    # Initial unique_id should have @22222222 suffix
    assert "@22222222" in initial_unique_id

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

    # Unique ID should have been migrated from @22222222 to @33333333
    expected_unique_id = initial_unique_id.replace("@22222222", "@33333333")
    assert entity_entry.unique_id == expected_unique_id

    # Entity should now be associated with the second sub-device
    bedroom_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_33333333")}
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
    """Test that entities are re-added as new when user renames device_id in YAML config."""
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
    # Should have @11111111 suffix
    assert "@11111111" in initial_unique_id

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

    # Unique ID should have the new device_id
    base_unique_id = initial_unique_id.replace("@11111111", "")
    expected_unique_id = f"{base_unique_id}@99999999"
    assert entity_entry.unique_id == expected_unique_id

    # Entity should be associated with the new device
    renamed_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{device.device_info.mac_address}_99999999")}
    )
    assert renamed_device is not None
    assert entity_entry.device_id == renamed_device.id


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
