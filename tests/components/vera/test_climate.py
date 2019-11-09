"""Vera tests."""

import requests_mock

from homeassistant.core import HomeAssistant

from .common import (
    DEVICE_THERMOSTAT_ID,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    assert_state,
    async_call_service,
    async_configure_component,
    update_device,
)


async def test_climate(hass: HomeAssistant) -> None:
    """Test function."""
    with requests_mock.mock(case_sensitive=True) as mocker:
        component_data = await async_configure_component(
            hass=hass,
            requests_mocker=mocker,
            response_sdata=RESPONSE_SDATA,
            response_status=RESPONSE_STATUS,
            respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
        )

        # Thermostat
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
