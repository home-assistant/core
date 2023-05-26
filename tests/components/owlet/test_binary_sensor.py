"""Test Owlet Sensor."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_binary_sensors_asleep(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_asleep.json"
    )

    assert len(hass.states.async_all("binary_sensor")) == 10

    assert hass.states.get("binary_sensor.owlet_baby_care_sock_awake").state == "off"


async def test_sensors_charging(hass: HomeAssistant) -> None:
    """Test sensor values charging."""
    await async_init_integration(
        hass, properties_fixture="update_properties_charging.json"
    )

    assert len(hass.states.async_all("binary_sensor")) == 10

    assert hass.states.get("binary_sensor.owlet_baby_care_sock_charging").state == "on"
    assert (
        hass.states.get(
            "binary_sensor.owlet_baby_care_sock_high_heart_rate_alert"
        ).state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_heart_rate_alert").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_high_oxygen_alert").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_oxygen_alert").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_battery_alert").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_lost_power_alert").state
        == "off"
    )
    assert (
        hass.states.get(
            "binary_sensor.owlet_baby_care_sock_sock_disconnected_alert"
        ).state
        == "off"
    )
    assert hass.states.get("binary_sensor.owlet_baby_care_sock_sock_off").state == "off"

    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_awake").state == "unknown"
    )


async def test_sensors_awake(hass: HomeAssistant) -> None:
    """Test sensor values awake."""
    await async_init_integration(
        hass, properties_fixture="update_properties_awake.json"
    )

    assert len(hass.states.async_all("binary_sensor")) == 10

    assert hass.states.get("binary_sensor.owlet_baby_care_sock_charging").state == "off"
    assert (
        hass.states.get(
            "binary_sensor.owlet_baby_care_sock_high_heart_rate_alert"
        ).state
        == "on"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_heart_rate_alert").state
        == "on"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_high_oxygen_alert").state
        == "on"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_oxygen_alert").state
        == "on"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_battery_alert").state
        == "on"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_lost_power_alert").state
        == "on"
    )
    assert (
        hass.states.get(
            "binary_sensor.owlet_baby_care_sock_sock_disconnected_alert"
        ).state
        == "off"
    )
    assert hass.states.get("binary_sensor.owlet_baby_care_sock_sock_off").state == "off"

    assert hass.states.get("binary_sensor.owlet_baby_care_sock_awake").state == "on"


async def test_sensors_asleep(hass: HomeAssistant) -> None:
    """Test sensor values asleep."""
    await async_init_integration(
        hass, properties_fixture="update_properties_asleep.json"
    )

    assert len(hass.states.async_all("binary_sensor")) == 10

    assert hass.states.get("binary_sensor.owlet_baby_care_sock_charging").state == "off"
    assert (
        hass.states.get(
            "binary_sensor.owlet_baby_care_sock_high_heart_rate_alert"
        ).state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_heart_rate_alert").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_high_oxygen_alert").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_oxygen_alert").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_low_battery_alert").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.owlet_baby_care_sock_lost_power_alert").state
        == "off"
    )
    assert (
        hass.states.get(
            "binary_sensor.owlet_baby_care_sock_sock_disconnected_alert"
        ).state
        == "off"
    )
    assert hass.states.get("binary_sensor.owlet_baby_care_sock_sock_off").state == "off"

    assert hass.states.get("binary_sensor.owlet_baby_care_sock_awake").state == "off"
