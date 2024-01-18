"""Test the Tessie sensor platform."""
from homeassistant.components.tessie.sensor import DESCRIPTIONS
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .common import TEST_VEHICLE_STATE_ONLINE, setup_platform


async def test_sensors(hass: HomeAssistant) -> None:
    """Tests that the sensor entities are correct."""

    assert len(hass.states.async_all("sensor")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("sensor")) == len(DESCRIPTIONS)

    assert hass.states.get("sensor.test_battery_level").state == str(
        TEST_VEHICLE_STATE_ONLINE["charge_state"]["battery_level"]
    )
    assert hass.states.get("sensor.test_charge_energy_added").state == str(
        TEST_VEHICLE_STATE_ONLINE["charge_state"]["charge_energy_added"]
    )
    assert hass.states.get("sensor.test_shift_state").state == STATE_UNKNOWN
