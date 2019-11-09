"""Vera tests."""

import requests_mock

from homeassistant.core import HomeAssistant

from .common import (
    DEVICE_LOCK_ID,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    assert_state,
    async_call_service,
    async_configure_component,
)


async def test_lock(hass: HomeAssistant) -> None:
    """Test function."""
    with requests_mock.mock(case_sensitive=True) as mocker:
        component_data = await async_configure_component(
            hass=hass,
            requests_mocker=mocker,
            response_sdata=RESPONSE_SDATA,
            response_status=RESPONSE_STATUS,
            respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
        )

        # Lock
        assert_state(hass, component_data, DEVICE_LOCK_ID, "lock", "unlocked")
        await async_call_service(hass, component_data, DEVICE_LOCK_ID, "lock", "lock")
        assert_state(hass, component_data, DEVICE_LOCK_ID, "lock", "locked")
        await async_call_service(hass, component_data, DEVICE_LOCK_ID, "lock", "unlock")
        assert_state(hass, component_data, DEVICE_LOCK_ID, "lock", "unlocked")
