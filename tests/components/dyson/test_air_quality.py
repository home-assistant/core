"""Test the Dyson air quality component."""
import json
from unittest import mock

import asynctest
from libpurecool.dyson_pure_cool import DysonPureCool
from libpurecool.dyson_pure_state_v2 import DysonEnvironmentalSensorV2State

from homeassistant.components import dyson as dyson_parent
from homeassistant.components.air_quality import (
    ATTR_NO2,
    ATTR_PM_2_5,
    ATTR_PM_10,
    DOMAIN as AIQ_DOMAIN,
)
import homeassistant.components.dyson.air_quality as dyson
from homeassistant.helpers import discovery
from homeassistant.setup import async_setup_component

from .common import load_mock_device


def _get_dyson_purecool_device():
    """Return a valid device as provided by the Dyson web services."""
    device = mock.Mock(spec=DysonPureCool)
    load_mock_device(device)
    device.name = "Living room"
    device.environmental_state.particulate_matter_25 = "0014"
    device.environmental_state.particulate_matter_10 = "0025"
    device.environmental_state.nitrogen_dioxide = "0042"
    device.environmental_state.volatile_organic_compounds = "0035"
    return device


def _get_config():
    """Return a config dictionary."""
    return {
        dyson_parent.DOMAIN: {
            dyson_parent.CONF_USERNAME: "email",
            dyson_parent.CONF_PASSWORD: "password",
            dyson_parent.CONF_LANGUAGE: "GB",
            dyson_parent.CONF_DEVICES: [
                {"device_id": "XX-XXXXX-XX", "device_ip": "192.168.0.1"}
            ],
        }
    }


@asynctest.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
@asynctest.patch(
    "libpurecool.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purecool_device()],
)
async def test_purecool_aiq_attributes(devices, login, hass):
    """Test state attributes."""
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()
    fan_state = hass.states.get("air_quality.living_room")
    attributes = fan_state.attributes

    assert fan_state.state == "14"
    assert attributes[ATTR_PM_2_5] == 14
    assert attributes[ATTR_PM_10] == 25
    assert attributes[ATTR_NO2] == 42
    assert attributes[dyson.ATTR_VOC] == 35


@asynctest.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
@asynctest.patch(
    "libpurecool.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purecool_device()],
)
async def test_purecool_aiq_update_state(devices, login, hass):
    """Test state update."""
    device = devices.return_value[0]
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()
    event = {
        "msg": "ENVIRONMENTAL-CURRENT-SENSOR-DATA",
        "time": "2019-03-29T10:00:01.000Z",
        "data": {
            "pm10": "0080",
            "p10r": "0151",
            "hact": "0040",
            "va10": "0055",
            "p25r": "0161",
            "noxl": "0069",
            "pm25": "0035",
            "sltm": "OFF",
            "tact": "2960",
        },
    }
    device.environmental_state = DysonEnvironmentalSensorV2State(json.dumps(event))

    for call in device.add_message_listener.call_args_list:
        callback = call[0][0]
        if type(callback.__self__) == dyson.DysonAirSensor:
            callback(device.environmental_state)

    await hass.async_block_till_done()
    fan_state = hass.states.get("air_quality.living_room")
    attributes = fan_state.attributes

    assert fan_state.state == "35"
    assert attributes[ATTR_PM_2_5] == 35
    assert attributes[ATTR_PM_10] == 80
    assert attributes[ATTR_NO2] == 69
    assert attributes[dyson.ATTR_VOC] == 55


@asynctest.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
@asynctest.patch(
    "libpurecool.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purecool_device()],
)
async def test_purecool_component_setup_only_once(devices, login, hass):
    """Test if entities are created only once."""
    config = _get_config()
    await async_setup_component(hass, dyson_parent.DOMAIN, config)
    await hass.async_block_till_done()
    discovery.load_platform(hass, AIQ_DOMAIN, dyson_parent.DOMAIN, {}, config)
    await hass.async_block_till_done()

    assert len(hass.data[dyson.DYSON_AIQ_DEVICES]) == 1


@asynctest.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
@asynctest.patch(
    "libpurecool.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purecool_device()],
)
async def test_purecool_aiq_without_discovery(devices, login, hass):
    """Test if component correctly returns if discovery not set."""
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()
    add_entities_mock = mock.MagicMock()

    dyson.setup_platform(hass, None, add_entities_mock, None)

    assert add_entities_mock.call_count == 0


@asynctest.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
@asynctest.patch(
    "libpurecool.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purecool_device()],
)
async def test_purecool_aiq_empty_environment_state(devices, login, hass):
    """Test device with empty environmental state."""
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()
    device = hass.data[dyson.DYSON_AIQ_DEVICES][0]
    device._device.environmental_state = None

    assert device.state is None
    assert device.particulate_matter_2_5 is None
    assert device.particulate_matter_10 is None
    assert device.nitrogen_dioxide is None
    assert device.volatile_organic_compounds is None
