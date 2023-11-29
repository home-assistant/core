"""Tessie sensor platform tests."""
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .common import DOMAIN, TEST_VEHICLES, URL_VEHICLES, setup_platform

from tests.common import load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

STATES = load_json_object_fixture("vehicles.json", DOMAIN)["results"][0]["last_state"]


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Tests that the sensors are correct."""

    aioclient_mock.get(
        URL_VEHICLES,
        text=TEST_VEHICLES,
    )

    await setup_platform(hass)

    assert hass.states.get("sensor.homeassistant_battery_level").state == str(
        STATES["charge_state"]["battery_level"]
    )
    assert hass.states.get("sensor.homeassistant_battery_range").state == str(
        STATES["charge_state"]["battery_range"]
    )
    assert hass.states.get("sensor.homeassistant_charge_energy_added").state == str(
        STATES["charge_state"]["charge_energy_added"]
    )
    assert hass.states.get("sensor.homeassistant_speed").state == STATE_UNKNOWN
