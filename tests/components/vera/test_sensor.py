"""Vera tests."""

from homeassistant.core import HomeAssistant

from .common import (
    DEVICE_ALARM_SENSOR_ID,
    DEVICE_HUMIDITY_SENSOR_ID,
    DEVICE_LIGHT_SENSOR_ID,
    DEVICE_POWER_METER_SENSOR_ID,
    DEVICE_TEMP_SENSOR_ID,
    DEVICE_UV_SENSOR_ID,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    assert_state,
    async_configure_component,
    update_device,
)


async def test_sensor(hass: HomeAssistant) -> None:
    """Test function."""
    component_data = await async_configure_component(
        hass=hass,
        response_sdata=RESPONSE_SDATA,
        response_status=RESPONSE_STATUS,
        respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
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

    # Trippable sensor
    assert_state(hass, component_data, DEVICE_ALARM_SENSOR_ID, "sensor", "Not Tripped")
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
