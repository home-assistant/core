"""Vera tests."""

import requests_mock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get_registry
from .common import (
    async_configure_component,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    RESPONSE_LU_SDATA_EMPTY,
    DEVICE_POWER_METER_SENSOR_ID,
    DEVICE_HUMIDITY_SENSOR_ID,
    DEVICE_UV_SENSOR_ID,
    DEVICE_LIGHT_SENSOR_ID,
    DEVICE_SCENE_CONTROLLER_ID,
    DEVICE_LIGHT_ID,
    DEVICE_CURTAIN_ID,
    DEVICE_SWITCH_ID,
    DEVICE_SWITCH2_ID,
    DEVICE_DIMMER_ID,
    DEVICE_TEMP_SENSOR_ID,
    DEVICE_MOTION_SENSOR_ID,
    DEVICE_ALARM_SENSOR_ID,
    DEVICE_DOOR_SENSOR_ID,
    DEVICE_LOCK_ID,
    DEVICE_THERMOSTAT_ID,
    DEVICE_IGNORE,
    assert_state,
    update_device,
    get_entity_id,
    get_device,
    async_call_service,
)


async def test_full(hass: HomeAssistant) -> None:
    """Test component fully."""
    with requests_mock.mock(case_sensitive=True) as mocker:
        component_data = await async_configure_component(
            hass=hass,
            requests_mocker=mocker,
            response_sdata=RESPONSE_SDATA,
            response_status=RESPONSE_STATUS,
            respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
        )

        registry = await async_get_registry(hass)

        # Ignore device.
        ignore_device = get_device(DEVICE_IGNORE, component_data)
        entry = registry.async_get(get_entity_id(ignore_device, "switch"))
        assert entry is None

        # Door sensor.
        assert_state(hass, component_data, DEVICE_DOOR_SENSOR_ID, "switch", "off")
        await async_call_service(
            hass, component_data, DEVICE_DOOR_SENSOR_ID, "switch", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_DOOR_SENSOR_ID, "switch", "on")
        await async_call_service(
            hass, component_data, DEVICE_DOOR_SENSOR_ID, "switch", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_DOOR_SENSOR_ID, "switch", "off")

        assert_state(
            hass, component_data, DEVICE_DOOR_SENSOR_ID, "binary_sensor", "off"
        )
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_DOOR_SENSOR_ID,
            key="tripped",
            value="1",
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_DOOR_SENSOR_ID,
            platform="binary_sensor",
            expected_state="on",
        )

        # Motion sensor.
        assert_state(hass, component_data, DEVICE_MOTION_SENSOR_ID, "switch", "off")
        await async_call_service(
            hass, component_data, DEVICE_MOTION_SENSOR_ID, "switch", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_MOTION_SENSOR_ID, "switch", "on")
        await async_call_service(
            hass, component_data, DEVICE_MOTION_SENSOR_ID, "switch", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_MOTION_SENSOR_ID, "switch", "off")

        assert_state(
            hass, component_data, DEVICE_MOTION_SENSOR_ID, "binary_sensor", "off"
        )
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_MOTION_SENSOR_ID,
            key="tripped",
            value="1",
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_DOOR_SENSOR_ID,
            platform="binary_sensor",
            expected_state="on",
        )

        # Temperature sensor.
        assert_state(hass, component_data, DEVICE_TEMP_SENSOR_ID, "sensor", "57.00")
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_TEMP_SENSOR_ID,
            key="temperature",
            value="66.12",
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_TEMP_SENSOR_ID,
            platform="sensor",
            expected_state="66.12",
        )

        # Dimmer
        assert_state(hass, component_data, DEVICE_DIMMER_ID, "light", "off")
        await async_call_service(
            hass,
            component_data,
            DEVICE_DIMMER_ID,
            "light",
            "turn_on",
            {"brightness": 120},
        )
        assert_state(hass, component_data, DEVICE_DIMMER_ID, "light", "on")
        await async_call_service(
            hass, component_data, DEVICE_DIMMER_ID, "light", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_DIMMER_ID, "light", "off")

        # Light
        assert_state(hass, component_data, DEVICE_LIGHT_ID, "light", "off")
        await async_call_service(
            hass, component_data, DEVICE_LIGHT_ID, "light", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_LIGHT_ID, "light", "on")
        await async_call_service(
            hass,
            component_data,
            DEVICE_LIGHT_ID,
            "light",
            "turn_on",
            {"hs_color": [300, 70]},
        )
        assert_state(
            hass,
            component_data,
            DEVICE_LIGHT_ID,
            "light",
            expected_hs_color=(240.0, 100.0),
        )
        await async_call_service(
            hass, component_data, DEVICE_LIGHT_ID, "light", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_LIGHT_ID, "light", "off")

        # Switch
        assert_state(hass, component_data, DEVICE_SWITCH_ID, "switch", "off")
        await async_call_service(
            hass, component_data, DEVICE_SWITCH_ID, "switch", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_SWITCH_ID, "switch", "on")
        await async_call_service(
            hass, component_data, DEVICE_SWITCH_ID, "switch", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_SWITCH_ID, "switch", "off")

        # Switch 2
        assert_state(hass, component_data, DEVICE_SWITCH2_ID, "light", "off")
        await async_call_service(
            hass, component_data, DEVICE_SWITCH2_ID, "light", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_SWITCH2_ID, "light", "on")
        await async_call_service(
            hass, component_data, DEVICE_SWITCH2_ID, "light", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_SWITCH2_ID, "light", "off")

        # Lock
        assert_state(hass, component_data, DEVICE_LOCK_ID, "lock", "unlocked")
        await async_call_service(hass, component_data, DEVICE_LOCK_ID, "lock", "lock")
        assert_state(hass, component_data, DEVICE_LOCK_ID, "lock", "locked")
        await async_call_service(hass, component_data, DEVICE_LOCK_ID, "lock", "unlock")
        assert_state(hass, component_data, DEVICE_LOCK_ID, "lock", "unlocked")

        # Thermostat
        assert_state(hass, component_data, DEVICE_THERMOSTAT_ID, "switch", "off")
        await async_call_service(
            hass, component_data, DEVICE_THERMOSTAT_ID, "switch", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_THERMOSTAT_ID, "switch", "on")
        await async_call_service(
            hass, component_data, DEVICE_THERMOSTAT_ID, "switch", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_THERMOSTAT_ID, "switch", "off")

        assert_state(hass, component_data, DEVICE_THERMOSTAT_ID, "climate", "off")
        await async_call_service(
            hass, component_data, DEVICE_THERMOSTAT_ID, "climate", "turn_on"
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            platform="climate",
            expected_state="heat_cool",
        )
        await async_call_service(
            hass,
            component_data,
            DEVICE_THERMOSTAT_ID,
            "climate",
            "set_hvac_mode",
            {"hvac_mode": "heat"},
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            platform="climate",
            expected_state="heat",
        )
        await async_call_service(
            hass,
            component_data,
            DEVICE_THERMOSTAT_ID,
            "climate",
            "set_hvac_mode",
            {"hvac_mode": "cool"},
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            platform="climate",
            expected_state="cool",
        )

        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            platform="climate",
            expected_fan_mode="auto",
        )
        await async_call_service(
            hass,
            component_data,
            DEVICE_THERMOSTAT_ID,
            "climate",
            "set_fan_mode",
            {"fan_mode": "on"},
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            platform="climate",
            expected_fan_mode="on",
        )

        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            platform="climate",
            expected_temperature=None,
            expected_current_temperature=None,
        )
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            key="temperature",
            value="30",
        )
        await async_call_service(
            hass,
            component_data,
            DEVICE_THERMOSTAT_ID,
            "climate",
            "set_temperature",
            {"temperature": 25},
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            platform="climate",
            expected_temperature=25,
            expected_current_temperature=30,
        )

        await async_call_service(
            hass,
            component_data,
            DEVICE_THERMOSTAT_ID,
            "climate",
            "set_hvac_mode",
            {"hvac_mode": "off"},
        )
        assert_state(
            hass=hass,
            data=component_data,
            device_id=DEVICE_THERMOSTAT_ID,
            platform="climate",
            expected_state="off",
        )

        # Curtain
        assert_state(hass, component_data, DEVICE_CURTAIN_ID, "cover", "closed")
        await async_call_service(
            hass, component_data, DEVICE_CURTAIN_ID, "cover", "open_cover"
        )
        assert_state(hass, component_data, DEVICE_CURTAIN_ID, "cover", "open")
        await async_call_service(
            hass,
            component_data,
            DEVICE_CURTAIN_ID,
            "cover",
            "set_cover_position",
            {"position": 50},
        )
        assert_state(
            hass,
            component_data,
            DEVICE_CURTAIN_ID,
            "cover",
            expected_state="open",
            expected_current_position=50,
        )
        await async_call_service(
            hass, component_data, DEVICE_CURTAIN_ID, "cover", "stop_cover"
        )
        assert_state(hass, component_data, DEVICE_CURTAIN_ID, "cover", "open")
        await async_call_service(
            hass, component_data, DEVICE_CURTAIN_ID, "cover", "close_cover"
        )
        assert_state(
            hass,
            component_data,
            DEVICE_CURTAIN_ID,
            "cover",
            "closed",
            expected_current_position=0,
        )

        # Scene
        # Possible bug. Using the service against a scene does not result in an API call.
        await async_call_service(
            hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "scene", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "off")
        await async_call_service(
            hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "on")
        await async_call_service(
            hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "off")

        # Trippable sensor
        assert_state(
            hass, component_data, DEVICE_ALARM_SENSOR_ID, "sensor", "Not Tripped"
        )
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_ALARM_SENSOR_ID,
            key="tripped",
            value="1",
        )
        assert_state(hass, component_data, DEVICE_ALARM_SENSOR_ID, "sensor", "Tripped")

        # Light sensor
        assert_state(hass, component_data, DEVICE_LIGHT_SENSOR_ID, "sensor", "0")
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_LIGHT_SENSOR_ID,
            key="light",
            value="30",
        )
        assert_state(hass, component_data, DEVICE_LIGHT_SENSOR_ID, "sensor", "30")

        # UV sensor
        assert_state(hass, component_data, DEVICE_UV_SENSOR_ID, "sensor", "0")
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_UV_SENSOR_ID,
            key="light",
            value="23",
        )
        assert_state(hass, component_data, DEVICE_UV_SENSOR_ID, "sensor", "23")

        # Humidity sensor
        assert_state(hass, component_data, DEVICE_HUMIDITY_SENSOR_ID, "sensor", "0")
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_HUMIDITY_SENSOR_ID,
            key="humidity",
            value="32",
        )
        assert_state(hass, component_data, DEVICE_HUMIDITY_SENSOR_ID, "sensor", "32")

        # Power sensor
        assert_state(hass, component_data, DEVICE_POWER_METER_SENSOR_ID, "sensor", "0")
        await update_device(
            hass=hass,
            data=component_data,
            device_id=DEVICE_POWER_METER_SENSOR_ID,
            key="watts",
            value="66",
        )
        assert_state(hass, component_data, DEVICE_POWER_METER_SENSOR_ID, "sensor", "66")
