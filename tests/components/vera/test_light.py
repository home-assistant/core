"""Vera tests."""

import requests_mock

from homeassistant.core import HomeAssistant

from .common import (
    DEVICE_LIGHT_ID,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    assert_state,
    async_call_service,
    async_configure_component,
)


async def test_light(hass: HomeAssistant) -> None:
    """Test function."""
    with requests_mock.mock(case_sensitive=True) as mocker:
        component_data = await async_configure_component(
            hass=hass,
            requests_mocker=mocker,
            response_sdata=RESPONSE_SDATA,
            response_status=RESPONSE_STATUS,
            respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
        )

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
