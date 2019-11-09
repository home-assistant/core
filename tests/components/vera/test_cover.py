"""Vera tests."""

import requests_mock

from homeassistant.core import HomeAssistant

from .common import (
    DEVICE_CURTAIN_ID,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    assert_state,
    async_call_service,
    async_configure_component,
)


async def test_cover(hass: HomeAssistant) -> None:
    """Test function."""
    with requests_mock.mock(case_sensitive=True) as mocker:
        component_data = await async_configure_component(
            hass=hass,
            requests_mocker=mocker,
            response_sdata=RESPONSE_SDATA,
            response_status=RESPONSE_STATUS,
            respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
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
