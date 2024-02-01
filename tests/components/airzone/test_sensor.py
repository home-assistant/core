"""The sensor tests for the Airzone platform."""

import copy
from unittest.mock import patch

from aioairzone.const import API_DATA, API_SYSTEMS

from homeassistant.components.airzone.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .util import (
    HVAC_DHW_MOCK,
    HVAC_MOCK,
    HVAC_SYSTEMS_MOCK,
    HVAC_VERSION_MOCK,
    HVAC_WEBSERVER_MOCK,
    async_init_integration,
)

from tests.common import async_fire_time_changed


async def test_airzone_create_sensors(
    hass: HomeAssistant, entity_registry_enabled_by_default: None
) -> None:
    """Test creation of sensors."""

    await async_init_integration(hass)

    # Hot Water
    state = hass.states.get("sensor.airzone_dhw_temperature")
    assert state.state == "43"

    # WebServer
    state = hass.states.get("sensor.airzone_webserver_rssi")
    assert state.state == "-42"

    # Zones
    state = hass.states.get("sensor.despacho_temperature")
    assert state.state == "21.20"

    state = hass.states.get("sensor.despacho_humidity")
    assert state.state == "36"

    state = hass.states.get("sensor.dorm_1_temperature")
    assert state.state == "20.8"

    state = hass.states.get("sensor.dorm_1_humidity")
    assert state.state == "35"

    state = hass.states.get("sensor.dorm_2_temperature")
    assert state.state == "20.5"

    state = hass.states.get("sensor.dorm_2_humidity")
    assert state.state == "40"

    state = hass.states.get("sensor.dorm_ppal_temperature")
    assert state.state == "21.1"

    state = hass.states.get("sensor.dorm_ppal_humidity")
    assert state.state == "39"

    state = hass.states.get("sensor.salon_temperature")
    assert state.state == "19.6"

    state = hass.states.get("sensor.salon_humidity")
    assert state.state == "34"

    state = hass.states.get("sensor.airzone_2_1_temperature")
    assert state.state == "22.3"

    state = hass.states.get("sensor.airzone_2_1_humidity")
    assert state.state == "62"

    state = hass.states.get("sensor.dkn_plus_temperature")
    assert state.state == "21.7"

    state = hass.states.get("sensor.dkn_plus_humidity")
    assert state is None


async def test_airzone_sensors_availability(
    hass: HomeAssistant, entity_registry_enabled_by_default: None
) -> None:
    """Test sensors availability."""

    await async_init_integration(hass)

    HVAC_MOCK_UNAVAILABLE_ZONE = copy.deepcopy(HVAC_MOCK)
    del HVAC_MOCK_UNAVAILABLE_ZONE[API_SYSTEMS][0][API_DATA][1]

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
        return_value=HVAC_DHW_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK_UNAVAILABLE_ZONE,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
        return_value=HVAC_SYSTEMS_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_version",
        return_value=HVAC_VERSION_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
        return_value=HVAC_WEBSERVER_MOCK,
    ):
        async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.dorm_ppal_temperature")
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.dorm_ppal_humidity")
    assert state.state == STATE_UNAVAILABLE
