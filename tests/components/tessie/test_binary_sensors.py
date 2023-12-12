"""Test the Tessie binary sensor platform."""

from homeassistant.components.tessie.binary_sensor import DESCRIPTIONS
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .common import TEST_VEHICLE_STATE_ONLINE, setup_platform

OFFON = [STATE_OFF, STATE_ON]


async def test_binary_sensors(hass: HomeAssistant) -> None:
    """Tests that the sensors are correct."""

    assert len(hass.states.async_all("binary_sensor")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("binary_sensor")) == len(DESCRIPTIONS)

    assert (hass.states.get("binary_sensor.test_battery_heater").state == STATE_ON) == (
        TEST_VEHICLE_STATE_ONLINE["charge_state"]["battery_heater_on"]
    )

    assert (hass.states.get("binary_sensor.test_charging").state == STATE_ON) == (
        TEST_VEHICLE_STATE_ONLINE["charge_state"]["charging_state"] == "Charging"
    )

    assert (
        hass.states.get("binary_sensor.test_auto_seat_climate_left").state == STATE_ON
    ) == (TEST_VEHICLE_STATE_ONLINE["climate_state"]["auto_seat_climate_left"])
