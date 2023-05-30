"""Test Owlet Sensor."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_sensors_asleep(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_asleep.json"
    )

    assert len(hass.states.async_all("sensor")) == 8

    assert (
        hass.states.get("sensor.owlet_baby_care_sock_battery_percentage").state
        == "50.0"
    )
    assert (
        hass.states.get("sensor.owlet_baby_care_sock_battery_remaining").state
        == "400.0"
    )
    assert hass.states.get("sensor.owlet_baby_care_sock_heart_rate").state == "97.0"
    assert hass.states.get("sensor.owlet_baby_care_sock_o2_saturation").state == "99.0"
    assert (
        hass.states.get(
            "sensor.owlet_baby_care_sock_o2_saturation_10_minute_average"
        ).state
        == "97.0"
    )

    assert (
        hass.states.get("sensor.owlet_baby_care_sock_signal_strength").state == "30.0"
    )
    assert hass.states.get("sensor.owlet_baby_care_sock_skin_temperature").state == "34"
    assert (
        hass.states.get("sensor.owlet_baby_care_sock_sleep_state").state
        == "light_sleep"
    )


async def test_sensors_awake(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_awake.json"
    )

    assert len(hass.states.async_all("sensor")) == 8

    assert (
        hass.states.get("sensor.owlet_baby_care_sock_battery_percentage").state
        == "80.0"
    )
    assert (
        hass.states.get("sensor.owlet_baby_care_sock_battery_remaining").state
        == "600.0"
    )
    assert hass.states.get("sensor.owlet_baby_care_sock_heart_rate").state == "110.0"
    assert hass.states.get("sensor.owlet_baby_care_sock_o2_saturation").state == "98.0"
    assert (
        hass.states.get(
            "sensor.owlet_baby_care_sock_o2_saturation_10_minute_average"
        ).state
        == "98.0"
    )
    assert (
        hass.states.get("sensor.owlet_baby_care_sock_signal_strength").state == "34.0"
    )
    assert hass.states.get("sensor.owlet_baby_care_sock_skin_temperature").state == "35"
    assert hass.states.get("sensor.owlet_baby_care_sock_sleep_state").state == "awake"


async def test_sensors_charging(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_charging.json"
    )

    assert len(hass.states.async_all("sensor")) == 8

    assert (
        hass.states.get("sensor.owlet_baby_care_sock_battery_percentage").state
        == "100.0"
    )
    assert (
        hass.states.get("sensor.owlet_baby_care_sock_battery_remaining").state
        == "unknown"
    )
    assert hass.states.get("sensor.owlet_baby_care_sock_heart_rate").state == "unknown"
    assert (
        hass.states.get("sensor.owlet_baby_care_sock_o2_saturation").state == "unknown"
    )
    assert (
        hass.states.get(
            "sensor.owlet_baby_care_sock_o2_saturation_10_minute_average"
        ).state
        == "unknown"
    )

    assert (
        hass.states.get("sensor.owlet_baby_care_sock_signal_strength").state == "34.0"
    )
    assert (
        hass.states.get("sensor.owlet_baby_care_sock_skin_temperature").state
        == "unknown"
    )
    assert hass.states.get("sensor.owlet_baby_care_sock_sleep_state").state == "unknown"
