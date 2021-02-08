"""deCONZ binary sensor platform tests."""

from copy import deepcopy
from unittest.mock import patch

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_VIBRATION,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.deconz.const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_NEW_DEVICES,
    CONF_MASTER_GATEWAY,
    DOMAIN as DECONZ_DOMAIN,
)
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.components.deconz.services import SERVICE_DEVICE_REFRESH
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

SENSORS = {
    "1": {
        "id": "Presence sensor id",
        "name": "Presence sensor",
        "type": "ZHAPresence",
        "state": {"dark": False, "presence": False},
        "config": {"on": True, "reachable": True, "temperature": 10},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "id": "Temperature sensor id",
        "name": "Temperature sensor",
        "type": "ZHATemperature",
        "state": {"temperature": False},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "3": {
        "id": "CLIP presence sensor id",
        "name": "CLIP presence sensor",
        "type": "CLIPPresence",
        "state": {"presence": False},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
    "4": {
        "id": "Vibration sensor id",
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


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, BINARY_SENSOR_DOMAIN, {"binary_sensor": {"platform": DECONZ_DOMAIN}}
        )
        is True
    )
    assert DECONZ_DOMAIN not in hass.data


async def test_no_binary_sensors(hass):
    """Test that no sensors in deconz results in no sensor entities."""
    await setup_deconz_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass):
    """Test successful creation of binary sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 3
    presence_sensor = hass.states.get("binary_sensor.presence_sensor")
    assert presence_sensor.state == STATE_OFF
    assert presence_sensor.attributes["device_class"] == DEVICE_CLASS_MOTION
    assert hass.states.get("binary_sensor.temperature_sensor") is None
    assert hass.states.get("binary_sensor.clip_presence_sensor") is None
    vibration_sensor = hass.states.get("binary_sensor.vibration_sensor")
    assert vibration_sensor.state == STATE_ON
    assert vibration_sensor.attributes["device_class"] == DEVICE_CLASS_VIBRATION

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"presence": True},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_ON

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_allow_clip_sensor(hass):
    """Test that CLIP sensors can be allowed."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    config_entry = await setup_deconz_integration(
        hass,
        options={CONF_ALLOW_CLIP_SENSOR: True},
        get_state_response=data,
    )

    assert len(hass.states.async_all()) == 4
    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_OFF
    assert hass.states.get("binary_sensor.temperature_sensor") is None
    assert hass.states.get("binary_sensor.clip_presence_sensor").state == STATE_OFF
    assert hass.states.get("binary_sensor.vibration_sensor").state == STATE_ON

    # Disallow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("binary_sensor.clip_presence_sensor") is None

    # Allow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 4
    assert hass.states.get("binary_sensor.clip_presence_sensor").state == STATE_OFF


async def test_add_new_binary_sensor(hass):
    """Test that adding a new binary sensor works."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)
    assert len(hass.states.async_all()) == 0

    state_added_event = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": deepcopy(SENSORS["1"]),
    }
    gateway.api.event_handler(state_added_event)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("binary_sensor.presence_sensor").state == STATE_OFF


async def test_add_new_binary_sensor_ignored(hass):
    """Test that adding a new binary sensor is not allowed."""
    config_entry = await setup_deconz_integration(
        hass,
        options={CONF_MASTER_GATEWAY: True, CONF_ALLOW_NEW_DEVICES: False},
    )
    gateway = get_gateway_from_config_entry(hass, config_entry)
    assert len(hass.states.async_all()) == 0

    state_added_event = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": deepcopy(SENSORS["1"]),
    }
    gateway.api.event_handler(state_added_event)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert not hass.states.get("binary_sensor.presence_sensor")

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    assert (
        len(async_entries_for_config_entry(entity_registry, config_entry.entry_id)) == 0
    )

    with patch(
        "pydeconz.DeconzSession.request",
        return_value={
            "groups": {},
            "lights": {},
            "sensors": {"1": deepcopy(SENSORS["1"])},
        },
    ):
        await hass.services.async_call(DECONZ_DOMAIN, SERVICE_DEVICE_REFRESH)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("binary_sensor.presence_sensor")
