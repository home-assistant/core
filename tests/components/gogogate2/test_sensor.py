"""Tests for the GogoGate2 component."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from gogogate2_api import GogoGate2Api, ISmartGateApi
from gogogate2_api.common import (
    DoorMode,
    DoorStatus,
    GogoGate2ActivateResponse,
    GogoGate2Door,
    GogoGate2InfoResponse,
    ISmartGateDoor,
    ISmartGateInfoResponse,
    Network,
    Outputs,
    Wifi,
)

from homeassistant.components.gogogate2.const import DEVICE_TYPE_ISMARTGATE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


def _mocked_gogogate_sensor_response(battery_level: int, temperature: float):
    return GogoGate2InfoResponse(
        user="user1",
        gogogatename="gogogatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc123.blah.blah",
        firmwareversion="",
        apicode="",
        door1=GogoGate2Door(
            door_id=1,
            permission=True,
            name="Door1",
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.OPENED,
            sensor=True,
            sensorid="ABCD",
            camera=False,
            events=2,
            temperature=temperature,
            voltage=battery_level,
        ),
        door2=GogoGate2Door(
            door_id=2,
            permission=True,
            name="Door2",
            gate=True,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid="WIRE",
            camera=False,
            events=0,
            temperature=temperature,
            voltage=battery_level,
        ),
        door3=GogoGate2Door(
            door_id=3,
            permission=True,
            name="Door3",
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=temperature,
            voltage=battery_level,
        ),
        outputs=Outputs(output1=True, output2=False, output3=True),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )


def _mocked_ismartgate_sensor_response(battery_level: int, temperature: float):
    return ISmartGateInfoResponse(
        user="user1",
        ismartgatename="ismartgatename0",
        model="ismartgatePRO",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc321.blah.blah",
        firmwareversion="555",
        pin=123,
        lang="en",
        newfirmware=False,
        door1=ISmartGateDoor(
            door_id=1,
            permission=True,
            name="Door1",
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid="ABCD",
            camera=False,
            events=2,
            temperature=temperature,
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=battery_level,
        ),
        door2=ISmartGateDoor(
            door_id=2,
            permission=True,
            name="Door2",
            gate=True,
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid="WIRE",
            camera=False,
            events=2,
            temperature=temperature,
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=battery_level,
        ),
        door3=ISmartGateDoor(
            door_id=3,
            permission=True,
            name="Door3",
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=temperature,
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=battery_level,
        ),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )


@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_sensor_update(gogogate2api_mock, hass: HomeAssistant) -> None:
    """Test data update."""

    bat_attributes = {
        "device_class": "battery",
        "door_id": 1,
        "friendly_name": "Door1 battery",
        "sensor_id": "ABCD",
    }
    temp_attributes = {
        "device_class": "temperature",
        "door_id": 1,
        "friendly_name": "Door1 temperature",
        "sensor_id": "ABCD",
        "unit_of_measurement": "°C",
    }

    api = MagicMock(GogoGate2Api)
    api.async_activate.return_value = GogoGate2ActivateResponse(result=True)
    api.async_info.return_value = _mocked_gogogate_sensor_response(25, 7.0)
    gogogate2api_mock.return_value = api

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    assert hass.states.get("cover.door1") is None
    assert hass.states.get("cover.door2") is None
    assert hass.states.get("cover.door3") is None
    assert hass.states.get("sensor.door1_battery") is None
    assert hass.states.get("sensor.door2_battery") is None
    assert hass.states.get("sensor.door3_battery") is None
    assert hass.states.get("sensor.door1_temperature") is None
    assert hass.states.get("sensor.door2_temperature") is None
    assert hass.states.get("sensor.door3_temperature") is None
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1")
    assert hass.states.get("cover.door2")
    assert hass.states.get("cover.door3")
    assert hass.states.get("sensor.door1_battery").state == "25"
    assert dict(hass.states.get("sensor.door1_battery").attributes) == bat_attributes
    assert hass.states.get("sensor.door2_battery") is None
    assert hass.states.get("sensor.door2_battery") is None
    assert hass.states.get("sensor.door1_temperature").state == "7.0"
    assert (
        dict(hass.states.get("sensor.door1_temperature").attributes) == temp_attributes
    )
    assert hass.states.get("sensor.door2_temperature") is None
    assert hass.states.get("sensor.door3_temperature") is None

    api.async_info.return_value = _mocked_gogogate_sensor_response(40, 10.0)
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.door1_battery").state == "40"
    assert hass.states.get("sensor.door1_temperature").state == "10.0"

    api.async_info.return_value = _mocked_gogogate_sensor_response(None, None)
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.door1_battery").state == STATE_UNKNOWN
    assert hass.states.get("sensor.door1_temperature").state == STATE_UNKNOWN

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert not hass.states.async_entity_ids(DOMAIN)


@patch("homeassistant.components.gogogate2.common.ISmartGateApi")
async def test_availability(ismartgateapi_mock, hass: HomeAssistant) -> None:
    """Test availability."""
    bat_attributes = {
        "device_class": "battery",
        "door_id": 1,
        "friendly_name": "Door1 battery",
        "sensor_id": "ABCD",
    }
    temp_attributes = {
        "device_class": "temperature",
        "door_id": 1,
        "friendly_name": "Door1 temperature",
        "sensor_id": "ABCD",
        "unit_of_measurement": "°C",
    }

    sensor_response = _mocked_ismartgate_sensor_response(35, -4.0)
    api = MagicMock(ISmartGateApi)
    api.async_info.return_value = sensor_response
    ismartgateapi_mock.return_value = api

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    assert hass.states.get("cover.door1") is None
    assert hass.states.get("cover.door2") is None
    assert hass.states.get("cover.door3") is None
    assert hass.states.get("sensor.door1_battery") is None
    assert hass.states.get("sensor.door2_battery") is None
    assert hass.states.get("sensor.door3_battery") is None
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1")
    assert hass.states.get("cover.door2")
    assert hass.states.get("cover.door3")
    assert hass.states.get("sensor.door1_battery").state == "35"
    assert hass.states.get("sensor.door2_battery") is None
    assert hass.states.get("sensor.door3_battery") is None
    assert hass.states.get("sensor.door1_temperature").state == "-4.0"
    assert hass.states.get("sensor.door2_temperature") is None
    assert hass.states.get("sensor.door3_temperature") is None
    assert (
        hass.states.get("sensor.door1_battery").attributes[ATTR_DEVICE_CLASS]
        == DEVICE_CLASS_BATTERY
    )
    assert (
        hass.states.get("sensor.door1_temperature").attributes[ATTR_DEVICE_CLASS]
        == DEVICE_CLASS_TEMPERATURE
    )
    assert (
        hass.states.get("sensor.door1_temperature").attributes[ATTR_UNIT_OF_MEASUREMENT]
        == "°C"
    )

    api.async_info.side_effect = Exception("Error")

    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.door1_battery").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.door1_temperature").state == STATE_UNAVAILABLE

    api.async_info.side_effect = None
    api.async_info.return_value = sensor_response
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.door1_battery").state == "35"
    assert dict(hass.states.get("sensor.door1_battery").attributes) == bat_attributes
    assert (
        dict(hass.states.get("sensor.door1_temperature").attributes) == temp_attributes
    )
