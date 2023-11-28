"""Aussie Broadband sensor platform tests."""
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_sensors(hass: HomeAssistant) -> None:
    """Tests that the sensors are correct."""

    await setup_platform(
        hass,
        [SENSOR_DOMAIN],
    )

    assert hass.states.get("sensor.fake_abb_nbn_service_data_used").state == "54321"
    assert hass.states.get("sensor.fake_abb_nbn_service_downloaded").state == "50000"
    assert hass.states.get("sensor.fake_abb_nbn_service_uploaded").state == "4321"
    assert (
        hass.states.get("sensor.fake_abb_nbn_service_billing_cycle_length").state
        == "28"
    )
    assert (
        hass.states.get("sensor.fake_abb_nbn_service_billing_cycle_remaining").state
        == "25"
    )


async def test_phone_sensor_states(hass: HomeAssistant) -> None:
    """Tests that the sensors are correct."""

    await setup_platform(hass, [SENSOR_DOMAIN], usage=MOCK_MOBILE_USAGE)

    assert hass.states.get("sensor.fake_abb_mobile_service_national_calls").state == "1"
    assert hass.states.get("sensor.fake_abb_mobile_service_mobile_calls").state == "2"
    assert hass.states.get("sensor.fake_abb_mobile_service_sms_sent").state == "4"
    assert hass.states.get("sensor.fake_abb_mobile_service_data_used").state == "512"
    assert (
        hass.states.get("sensor.fake_abb_mobile_service_billing_cycle_length").state
        == "31"
    )
    assert (
        hass.states.get("sensor.fake_abb_mobile_service_billing_cycle_remaining").state
        == "30"
    )


async def test_voip_sensor_states(hass: HomeAssistant) -> None:
    """Tests that the sensors are correct."""

    await setup_platform(hass, [SENSOR_DOMAIN], usage=MOCK_VOIP_USAGE)

    assert hass.states.get("sensor.fake_abb_voip_service_national_calls").state == "1"
    assert (
        hass.states.get("sensor.fake_abb_voip_service_sms_sent").state == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.fake_abb_voip_service_data_used").state == STATE_UNKNOWN
    )
