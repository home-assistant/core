"""Tessie sensor platform tests."""
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .common import TEST_STATE_OF_ALL_VEHICLES, setup_platform

STATES = TEST_STATE_OF_ALL_VEHICLES["results"][0]["last_state"]


async def test_sensors(hass: HomeAssistant) -> None:
    """Tests that the sensors are correct."""

    assert len(hass.states.async_all("sensor")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("sensor")) == 10

    assert hass.states.get("sensor.test_battery_level")

    assert hass.states.get("sensor.test_battery_level").state == str(
        STATES["charge_state"]["battery_level"]
    )
    assert hass.states.get("sensor.test_battery_range").state == str(
        STATES["charge_state"]["battery_range"]
    )
    assert hass.states.get("sensor.test_charge_energy_added").state == str(
        STATES["charge_state"]["charge_energy_added"]
    )
    assert hass.states.get("sensor.test_speed").state == STATE_UNKNOWN
