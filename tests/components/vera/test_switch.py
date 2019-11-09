"""Vera tests."""

import requests_mock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get_registry

from .common import (
    DEVICE_DOOR_SENSOR_ID,
    DEVICE_IGNORE,
    DEVICE_MOTION_SENSOR_ID,
    DEVICE_SCENE_CONTROLLER_ID,
    DEVICE_SWITCH2_ID,
    DEVICE_SWITCH_ID,
    DEVICE_THERMOSTAT_ID,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    assert_state,
    async_call_service,
    async_configure_component,
    get_device,
    get_entity_id,
)


async def test_switch(hass: HomeAssistant) -> None:
    """Test function."""
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

        # Scene
        assert_state(hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "off")
        await async_call_service(
            hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "turn_on"
        )
        assert_state(hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "on")
        await async_call_service(
            hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "turn_off"
        )
        assert_state(hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "off")
