"""deCONZ binary sensor platform tests."""

from collections.abc import Callable
from typing import Any

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.deconz.const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_NEW_DEVICES,
    CONF_MASTER_GATEWAY,
    DOMAIN as DECONZ_DOMAIN,
)
from homeassistant.components.deconz.services import SERVICE_DEVICE_REFRESH
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import WebsocketDataType

TEST_DATA = [
    (  # Alarm binary sensor
        {
            "config": {
                "battery": 100,
                "on": True,
                "reachable": True,
                "temperature": 2600,
            },
            "ep": 1,
            "etag": "18c0f3c2100904e31a7f938db2ba9ba9",
            "manufacturername": "dresden elektronik",
            "modelid": "lumi.sensor_motion.aq2",
            "name": "Alarm 10",
            "state": {
                "alarm": False,
                "lastupdated": "none",
                "lowbattery": None,
                "tampered": None,
            },
            "swversion": "20170627",
            "type": "ZHAAlarm",
            "uniqueid": "00:15:8d:00:02:b5:d1:80-01-0500",
        },
        {
            "entity_count": 3,
            "device_count": 3,
            "entity_id": "binary_sensor.alarm_10",
            "unique_id": "00:15:8d:00:02:b5:d1:80-01-0500-alarm",
            "state": STATE_OFF,
            "entity_category": None,
            "device_class": BinarySensorDeviceClass.SAFETY,
            "attributes": {
                "on": True,
                "temperature": 26.0,
                "device_class": "safety",
                "friendly_name": "Alarm 10",
            },
            "websocket_event": {"alarm": True},
            "next_state": STATE_ON,
        },
    ),
    (  # Carbon monoxide binary sensor
        {
            "config": {
                "battery": 100,
                "on": True,
                "pending": [],
                "reachable": True,
            },
            "ep": 1,
            "etag": "b7599df551944df97b2aa87d160b9c45",
            "manufacturername": "Heiman",
            "modelid": "CO_V16",
            "name": "Cave CO",
            "state": {
                "carbonmonoxide": False,
                "lastupdated": "none",
                "lowbattery": False,
                "tampered": False,
            },
            "swversion": "20150330",
            "type": "ZHACarbonMonoxide",
            "uniqueid": "00:15:8d:00:02:a5:21:24-01-0101",
        },
        {
            "entity_count": 4,
            "device_count": 3,
            "entity_id": "binary_sensor.cave_co",
            "unique_id": "00:15:8d:00:02:a5:21:24-01-0101-carbon_monoxide",
            "state": STATE_OFF,
            "entity_category": None,
            "device_class": BinarySensorDeviceClass.CO,
            "attributes": {
                "on": True,
                "device_class": "carbon_monoxide",
                "friendly_name": "Cave CO",
            },
            "websocket_event": {"carbonmonoxide": True},
            "next_state": STATE_ON,
        },
    ),
    (  # Fire binary sensor
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "2b585d2c016bfd665ba27a8fdad28670",
            "manufacturername": "LUMI",
            "modelid": "lumi.sensor_smoke",
            "name": "sensor_kitchen_smoke",
            "state": {
                "fire": False,
                "lastupdated": "2018-02-20T11:25:02",
            },
            "type": "ZHAFire",
            "uniqueid": "00:15:8d:00:01:d9:3e:7c-01-0500",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "binary_sensor.sensor_kitchen_smoke",
            "unique_id": "00:15:8d:00:01:d9:3e:7c-01-0500-fire",
            "state": STATE_OFF,
            "entity_category": None,
            "device_class": BinarySensorDeviceClass.SMOKE,
            "attributes": {
                "on": True,
                "device_class": "smoke",
                "friendly_name": "sensor_kitchen_smoke",
            },
            "websocket_event": {"fire": True},
            "next_state": STATE_ON,
        },
    ),
    (  # Fire test mode binary sensor
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "2b585d2c016bfd665ba27a8fdad28670",
            "manufacturername": "LUMI",
            "modelid": "lumi.sensor_smoke",
            "name": "sensor_kitchen_smoke",
            "state": {
                "fire": False,
                "test": False,
                "lastupdated": "2018-02-20T11:25:02",
            },
            "type": "ZHAFire",
            "uniqueid": "00:15:8d:00:01:d9:3e:7c-01-0500",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "binary_sensor.sensor_kitchen_smoke_test_mode",
            "unique_id": "00:15:8d:00:01:d9:3e:7c-01-0500-in_test_mode",
            "state": STATE_OFF,
            "entity_category": EntityCategory.DIAGNOSTIC,
            "device_class": BinarySensorDeviceClass.SMOKE,
            "attributes": {
                "device_class": "smoke",
                "friendly_name": "sensor_kitchen_smoke Test Mode",
            },
            "websocket_event": {"test": True},
            "next_state": STATE_ON,
        },
    ),
    (  # Generic flag binary sensor
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "modelid": "Switch",
            "name": "Kitchen Switch",
            "state": {
                "flag": True,
                "lastupdated": "2018-07-01T10:40:35",
            },
            "swversion": "1.0.0",
            "type": "CLIPGenericFlag",
            "uniqueid": "kitchen-switch",
        },
        {
            "entity_count": 1,
            "device_count": 2,
            "entity_id": "binary_sensor.kitchen_switch",
            "unique_id": "kitchen-switch-flag",
            "state": STATE_ON,
            "entity_category": None,
            "device_class": None,
            "attributes": {
                "on": True,
                "friendly_name": "Kitchen Switch",
            },
            "websocket_event": {"flag": False},
            "next_state": STATE_OFF,
        },
    ),
    (  # Open/Close binary sensor
        {
            "config": {
                "battery": 95,
                "on": True,
                "reachable": True,
                "temperature": 3300,
            },
            "ep": 1,
            "etag": "66cc641d0368110da6882b50090174ac",
            "manufacturername": "LUMI",
            "modelid": "lumi.sensor_magnet.aq2",
            "name": "Back Door",
            "state": {
                "lastupdated": "2019-05-05T14:54:32",
                "open": False,
            },
            "swversion": "20161128",
            "type": "ZHAOpenClose",
            "uniqueid": "00:15:8d:00:02:2b:96:b4-01-0006",
        },
        {
            "entity_count": 3,
            "device_count": 3,
            "entity_id": "binary_sensor.back_door",
            "unique_id": "00:15:8d:00:02:2b:96:b4-01-0006-open",
            "state": STATE_OFF,
            "entity_category": None,
            "device_class": BinarySensorDeviceClass.OPENING,
            "attributes": {
                "on": True,
                "temperature": 33.0,
                "device_class": "opening",
                "friendly_name": "Back Door",
            },
            "websocket_event": {"open": True},
            "next_state": STATE_ON,
        },
    ),
    (  # Presence binary sensor
        {
            "config": {
                "alert": "none",
                "battery": 100,
                "delay": 0,
                "ledindication": False,
                "on": True,
                "pending": [],
                "reachable": True,
                "sensitivity": 1,
                "sensitivitymax": 2,
                "usertest": False,
            },
            "ep": 2,
            "etag": "5cfb81765e86aa53ace427cfd52c6d52",
            "manufacturername": "Philips",
            "modelid": "SML001",
            "name": "Motion sensor 4",
            "state": {
                "dark": False,
                "lastupdated": "2019-05-05T14:37:06",
                "presence": False,
            },
            "swversion": "6.1.0.18912",
            "type": "ZHAPresence",
            "uniqueid": "00:17:88:01:03:28:8c:9b-02-0406",
        },
        {
            "entity_count": 3,
            "device_count": 3,
            "entity_id": "binary_sensor.motion_sensor_4",
            "unique_id": "00:17:88:01:03:28:8c:9b-02-0406-presence",
            "state": STATE_OFF,
            "entity_category": None,
            "device_class": BinarySensorDeviceClass.MOTION,
            "attributes": {
                "on": True,
                "dark": False,
                "device_class": "motion",
                "friendly_name": "Motion sensor 4",
            },
            "websocket_event": {"presence": True},
            "next_state": STATE_ON,
        },
    ),
    (  # Water leak binary sensor
        {
            "config": {
                "battery": 100,
                "on": True,
                "reachable": True,
                "temperature": 2500,
            },
            "ep": 1,
            "etag": "fae893708dfe9b358df59107d944fa1c",
            "manufacturername": "LUMI",
            "modelid": "lumi.sensor_wleak.aq1",
            "name": "water2",
            "state": {
                "lastupdated": "2019-01-29T07:13:20",
                "lowbattery": False,
                "tampered": False,
                "water": False,
            },
            "swversion": "20170721",
            "type": "ZHAWater",
            "uniqueid": "00:15:8d:00:02:2f:07:db-01-0500",
        },
        {
            "entity_count": 5,
            "device_count": 3,
            "entity_id": "binary_sensor.water2",
            "unique_id": "00:15:8d:00:02:2f:07:db-01-0500-water",
            "state": STATE_OFF,
            "entity_category": None,
            "device_class": BinarySensorDeviceClass.MOISTURE,
            "attributes": {
                "on": True,
                "temperature": 25.0,
                "device_class": "moisture",
                "friendly_name": "water2",
            },
            "websocket_event": {"water": True},
            "next_state": STATE_ON,
        },
    ),
    (  # Vibration binary sensor
        {
            "config": {
                "battery": 91,
                "on": True,
                "pending": [],
                "reachable": True,
                "sensitivity": 21,
                "sensitivitymax": 21,
                "temperature": 3200,
            },
            "ep": 1,
            "etag": "b7599df551944df97b2aa87d160b9c45",
            "manufacturername": "LUMI",
            "modelid": "lumi.vibration.aq1",
            "name": "Vibration 1",
            "state": {
                "lastupdated": "2019-03-09T15:53:07",
                "orientation": [10, 1059, 0],
                "tiltangle": 83,
                "vibration": True,
                "vibrationstrength": 114,
            },
            "swversion": "20180130",
            "type": "ZHAVibration",
            "uniqueid": "00:15:8d:00:02:a5:21:24-01-0101",
        },
        {
            "entity_count": 3,
            "device_count": 3,
            "entity_id": "binary_sensor.vibration_1",
            "unique_id": "00:15:8d:00:02:a5:21:24-01-0101-vibration",
            "state": STATE_ON,
            "entity_category": None,
            "device_class": BinarySensorDeviceClass.VIBRATION,
            "attributes": {
                "on": True,
                "temperature": 32.0,
                "orientation": [10, 1059, 0],
                "tiltangle": 83,
                "vibrationstrength": 114,
                "device_class": "vibration",
                "friendly_name": "Vibration 1",
            },
            "websocket_event": {"vibration": False},
            "next_state": STATE_OFF,
        },
    ),
    (  # Tampering binary sensor
        {
            "name": "Presence sensor",
            "type": "ZHAPresence",
            "state": {
                "dark": False,
                "lowbattery": False,
                "presence": False,
                "tampered": False,
            },
            "config": {
                "on": True,
                "reachable": True,
                "temperature": 10,
            },
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        },
        {
            "entity_count": 4,
            "device_count": 3,
            "entity_id": "binary_sensor.presence_sensor_tampered",
            "unique_id": "00:00:00:00:00:00:00:00-00-tampered",
            "state": STATE_OFF,
            "entity_category": EntityCategory.DIAGNOSTIC,
            "device_class": BinarySensorDeviceClass.TAMPER,
            "attributes": {
                "device_class": "tamper",
                "friendly_name": "Presence sensor Tampered",
            },
            "websocket_event": {"tampered": True},
            "next_state": STATE_ON,
        },
    ),
    (  # Low battery binary sensor
        {
            "name": "Presence sensor",
            "type": "ZHAPresence",
            "state": {
                "dark": False,
                "lowbattery": False,
                "presence": False,
                "tampered": False,
            },
            "config": {
                "on": True,
                "reachable": True,
                "temperature": 10,
            },
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        },
        {
            "entity_count": 4,
            "device_count": 3,
            "entity_id": "binary_sensor.presence_sensor_low_battery",
            "unique_id": "00:00:00:00:00:00:00:00-00-low_battery",
            "state": STATE_OFF,
            "entity_category": EntityCategory.DIAGNOSTIC,
            "device_class": BinarySensorDeviceClass.BATTERY,
            "attributes": {
                "device_class": "battery",
                "friendly_name": "Presence sensor Low Battery",
            },
            "websocket_event": {"lowbattery": True},
            "next_state": STATE_ON,
        },
    ),
]


@pytest.mark.parametrize("config_entry_options", [{CONF_ALLOW_CLIP_SENSOR: True}])
@pytest.mark.parametrize(("sensor_1_payload", "expected"), TEST_DATA)
async def test_binary_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_setup: ConfigEntry,
    mock_websocket_data: WebsocketDataType,
    expected: dict[str, Any],
) -> None:
    """Test successful creation of binary sensor entities."""
    assert len(hass.states.async_all()) == expected["entity_count"]

    # Verify state data

    sensor = hass.states.get(expected["entity_id"])
    assert sensor.state == expected["state"]
    assert sensor.attributes.get(ATTR_DEVICE_CLASS) == expected["device_class"]
    assert sensor.attributes == expected["attributes"]

    # Verify entity registry data

    ent_reg_entry = entity_registry.async_get(expected["entity_id"])
    assert ent_reg_entry.entity_category is expected["entity_category"]
    assert ent_reg_entry.unique_id == expected["unique_id"]

    # Verify device registry data

    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == expected["device_count"]
    )

    # Change state

    event_changed_sensor = {
        "r": "sensors",
        "id": "1",
        "state": expected["websocket_event"],
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()
    assert hass.states.get(expected["entity_id"]).state == expected["next_state"]

    # Unload entry

    await hass.config_entries.async_unload(config_entry_setup.entry_id)
    assert hass.states.get(expected["entity_id"]).state == STATE_UNAVAILABLE

    # Remove entry

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "sensor_1_payload",
    [
        {
            "name": "CLIP presence sensor",
            "type": "CLIPPresence",
            "state": {"presence": False},
            "config": {},
            "uniqueid": "00:00:00:00:00:00:00:02-00",
        }
    ],
)
@pytest.mark.parametrize("config_entry_options", [{CONF_ALLOW_CLIP_SENSOR: False}])
@pytest.mark.usefixtures("config_entry_setup")
async def test_not_allow_clip_sensor(hass: HomeAssistant) -> None:
    """Test that CLIP sensors are not allowed."""
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "1": {
                "name": "Presence sensor",
                "type": "ZHAPresence",
                "state": {"presence": False},
                "config": {"on": True, "reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "name": "CLIP presence sensor",
                "type": "CLIPPresence",
                "state": {"presence": False},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
            "3": {
                "config": {"on": True, "reachable": True},
                "etag": "fda064fca03f17389d0799d7cb1883ee",
                "manufacturername": "Philips",
                "modelid": "CLIPGenericFlag",
                "name": "Clip Flag Boot Time",
                "state": {"flag": True, "lastupdated": "2021-09-30T07:09:06.281"},
                "swversion": "1.0",
                "type": "CLIPGenericFlag",
                "uniqueid": "/sensors/3",
            },
        }
    ],
)
@pytest.mark.parametrize("config_entry_options", [{CONF_ALLOW_CLIP_SENSOR: True}])
async def test_allow_clip_sensor(hass: HomeAssistant, config_entry_setup) -> None:
    """Test that CLIP sensors can be allowed."""

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_OFF
    assert hass.states.get("binary_sensor.clip_presence_sensor").state == STATE_OFF
    assert hass.states.get("binary_sensor.clip_flag_boot_time").state == STATE_ON

    # Disallow clip sensors

    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert not hass.states.get("binary_sensor.clip_presence_sensor")
    assert not hass.states.get("binary_sensor.clip_flag_boot_time")

    # Allow clip sensors

    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("binary_sensor.clip_presence_sensor").state == STATE_OFF
    assert hass.states.get("binary_sensor.clip_flag_boot_time").state == STATE_ON


@pytest.mark.usefixtures("config_entry_setup")
async def test_add_new_binary_sensor(
    hass: HomeAssistant,
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that adding a new binary sensor works."""
    assert len(hass.states.async_all()) == 0

    event_added_sensor = {
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": {
            "id": "Presence sensor id",
            "name": "Presence sensor",
            "type": "ZHAPresence",
            "state": {"presence": False},
            "config": {"on": True, "reachable": True},
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        },
    }
    await mock_websocket_data(event_added_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_OFF


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_MASTER_GATEWAY: True, CONF_ALLOW_NEW_DEVICES: False}]
)
async def test_add_new_binary_sensor_ignored_load_entities_on_service_call(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_setup: ConfigEntry,
    deconz_payload: dict[str, Any],
    mock_requests: Callable[[str], None],
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that adding a new binary sensor is not allowed."""
    sensor = {
        "name": "Presence sensor",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {"on": True, "reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    }
    event_added_sensor = {
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": sensor,
    }

    assert len(hass.states.async_all()) == 0

    await mock_websocket_data(event_added_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert not hass.states.get("binary_sensor.presence_sensor")

    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, config_entry_setup.entry_id
            )
        )
        == 0
    )

    deconz_payload["sensors"] = {"1": sensor}
    mock_requests()

    await hass.services.async_call(DECONZ_DOMAIN, SERVICE_DEVICE_REFRESH)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("binary_sensor.presence_sensor")


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_MASTER_GATEWAY: True, CONF_ALLOW_NEW_DEVICES: False}]
)
async def test_add_new_binary_sensor_ignored_load_entities_on_options_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_setup: ConfigEntry,
    deconz_payload: dict[str, Any],
    mock_requests: Callable[[str], None],
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that adding a new binary sensor is not allowed."""
    sensor = {
        "name": "Presence sensor",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {"on": True, "reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    }
    event_added_sensor = {
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": sensor,
    }

    assert len(hass.states.async_all()) == 0

    await mock_websocket_data(event_added_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert not hass.states.get("binary_sensor.presence_sensor")

    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, config_entry_setup.entry_id
            )
        )
        == 0
    )

    deconz_payload["sensors"] = {"1": sensor}
    mock_requests()

    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_ALLOW_NEW_DEVICES: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("binary_sensor.presence_sensor")
