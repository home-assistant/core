"""deCONZ binary sensor platform tests."""

from unittest.mock import patch

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_VIBRATION,
)
from homeassistant.components.deconz.const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_NEW_DEVICES,
    CONF_MASTER_GATEWAY,
    DOMAIN as DECONZ_DOMAIN,
)
from homeassistant.components.deconz.services import SERVICE_DEVICE_REFRESH
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    DEVICE_CLASS_TEMPERATURE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import async_entries_for_config_entry

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_request,
    setup_deconz_integration,
)


async def test_no_binary_sensors(hass, aioclient_mock):
    """Test that no sensors in deconz results in no sensor entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass, aioclient_mock, mock_deconz_websocket):
    """Test successful creation of binary sensor entities."""
    data = {
        "sensors": {
            "1": {
                "name": "Presence sensor",
                "type": "ZHAPresence",
                "state": {"dark": False, "presence": False},
                "config": {"on": True, "reachable": True, "temperature": 10},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "name": "Temperature sensor",
                "type": "ZHATemperature",
                "state": {"temperature": False},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "3": {
                "name": "CLIP presence sensor",
                "type": "CLIPPresence",
                "state": {"presence": False},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
            "4": {
                "name": "Vibration sensor",
                "type": "ZHAVibration",
                "state": {
                    "orientation": [1, 2, 3],
                    "tiltangle": 36,
                    "vibration": True,
                    "vibrationstrength": 10,
                },
                "config": {"on": True, "reachable": True, "temperature": 10},
                "uniqueid": "00:00:00:00:00:00:00:03-00",
            },
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 5
    presence_sensor = hass.states.get("binary_sensor.presence_sensor")
    assert presence_sensor.state == STATE_OFF
    assert presence_sensor.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_MOTION
    presence_temp = hass.states.get("sensor.presence_sensor_temperature")
    assert presence_temp.state == "0.1"
    assert presence_temp.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_TEMPERATURE
    assert hass.states.get("binary_sensor.temperature_sensor") is None
    assert hass.states.get("binary_sensor.clip_presence_sensor") is None
    vibration_sensor = hass.states.get("binary_sensor.vibration_sensor")
    assert vibration_sensor.state == STATE_ON
    assert vibration_sensor.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_VIBRATION
    vibration_temp = hass.states.get("sensor.vibration_sensor_temperature")
    assert vibration_temp.state == "0.1"
    assert vibration_temp.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_TEMPERATURE

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"presence": True},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_ON

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


async def test_tampering_sensor(hass, aioclient_mock, mock_deconz_websocket):
    """Verify tampering sensor works."""
    data = {
        "sensors": {
            "1": {
                "name": "Presence sensor",
                "type": "ZHAPresence",
                "state": {"dark": False, "presence": False, "tampered": False},
                "config": {"on": True, "reachable": True, "temperature": 10},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 3
    presence_tamper = hass.states.get("binary_sensor.presence_sensor_tampered")
    assert presence_tamper.state == STATE_OFF
    assert presence_tamper.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_PROBLEM

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"tampered": True},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.presence_sensor_tampered").state == STATE_ON

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert (
        hass.states.get("binary_sensor.presence_sensor_tampered").state
        == STATE_UNAVAILABLE
    )

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


async def test_allow_clip_sensor(hass, aioclient_mock):
    """Test that CLIP sensors can be allowed."""
    data = {
        "sensors": {
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
        }
    }

    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(
            hass, aioclient_mock, options={CONF_ALLOW_CLIP_SENSOR: True}
        )

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_OFF
    assert hass.states.get("binary_sensor.clip_presence_sensor").state == STATE_OFF

    # Disallow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert not hass.states.get("binary_sensor.clip_presence_sensor")

    # Allow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("binary_sensor.clip_presence_sensor").state == STATE_OFF


async def test_add_new_binary_sensor(hass, aioclient_mock, mock_deconz_websocket):
    """Test that adding a new binary sensor works."""
    event_added_sensor = {
        "t": "event",
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

    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0

    await mock_deconz_websocket(data=event_added_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_OFF


async def test_add_new_binary_sensor_ignored(
    hass, aioclient_mock, mock_deconz_websocket
):
    """Test that adding a new binary sensor is not allowed."""
    sensor = {
        "name": "Presence sensor",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {"on": True, "reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    }
    event_added_sensor = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": sensor,
    }

    config_entry = await setup_deconz_integration(
        hass,
        aioclient_mock,
        options={CONF_MASTER_GATEWAY: True, CONF_ALLOW_NEW_DEVICES: False},
    )

    assert len(hass.states.async_all()) == 0

    await mock_deconz_websocket(data=event_added_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert not hass.states.get("binary_sensor.presence_sensor")

    entity_registry = er.async_get(hass)
    assert (
        len(async_entries_for_config_entry(entity_registry, config_entry.entry_id)) == 0
    )

    aioclient_mock.clear_requests()
    data = {"groups": {}, "lights": {}, "sensors": {"1": sensor}}
    mock_deconz_request(aioclient_mock, config_entry.data, data)

    await hass.services.async_call(DECONZ_DOMAIN, SERVICE_DEVICE_REFRESH)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("binary_sensor.presence_sensor")
