"""Vera tests."""

import requests_mock

from homeassistant.core import HomeAssistant

from .common import (
    DEVICE_DOOR_SENSOR_ID,
    DEVICE_MOTION_SENSOR_ID,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    assert_state,
    async_configure_component,
    update_device,
)


async def test_binary_sensor(hass: HomeAssistant) -> None:
    """Test function."""
    with requests_mock.mock(case_sensitive=True) as mocker:
        component_data = await async_configure_component(
            hass=hass,
            requests_mocker=mocker,
            response_sdata=RESPONSE_SDATA,
            response_status=RESPONSE_STATUS,
            respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
        )

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
