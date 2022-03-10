"""Tests for the Airzone integration."""

from unittest.mock import patch

from aioairzone.const import (
    API_AIR_DEMAND,
    API_COLD_STAGE,
    API_COLD_STAGES,
    API_DATA,
    API_ERRORS,
    API_FLOOR_DEMAND,
    API_HEAT_STAGE,
    API_HEAT_STAGES,
    API_HUMIDITY,
    API_MAX_TEMP,
    API_MIN_TEMP,
    API_MODE,
    API_MODES,
    API_NAME,
    API_ON,
    API_ROOM_TEMP,
    API_SET_POINT,
    API_SYSTEM_ID,
    API_SYSTEMS,
    API_UNITS,
    API_ZONE_ID,
)

from homeassistant.components.airzone import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 3000,
}

HVAC_MOCK = {
    API_SYSTEMS: [
        {
            API_DATA: [
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 1,
                    API_NAME: "Salon",
                    API_ON: 0,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19.5,
                    API_ROOM_TEMP: 19.6,
                    API_MODES: [1, 4, 2, 3, 5],
                    API_MODE: 3,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 1,
                    API_HEAT_STAGE: 1,
                    API_HUMIDITY: 34,
                    API_UNITS: 0,
                    API_ERRORS: [],
                    API_AIR_DEMAND: 0,
                    API_FLOOR_DEMAND: 0,
                },
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 2,
                    API_NAME: "Dorm Ppal",
                    API_ON: 0,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19.5,
                    API_ROOM_TEMP: 21.1,
                    API_MODE: 3,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 1,
                    API_HEAT_STAGE: 1,
                    API_HUMIDITY: 39,
                    API_UNITS: 0,
                    API_ERRORS: [],
                    API_AIR_DEMAND: 0,
                    API_FLOOR_DEMAND: 0,
                },
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 3,
                    API_NAME: "Dorm #1",
                    API_ON: 0,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19.5,
                    API_ROOM_TEMP: 20.8,
                    API_MODE: 3,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 1,
                    API_HEAT_STAGE: 1,
                    API_HUMIDITY: 35,
                    API_UNITS: 0,
                    API_ERRORS: [],
                    API_AIR_DEMAND: 0,
                    API_FLOOR_DEMAND: 0,
                },
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 4,
                    API_NAME: "Despacho",
                    API_ON: 0,
                    API_MAX_TEMP: 86,
                    API_MIN_TEMP: 59,
                    API_SET_POINT: 67.1,
                    API_ROOM_TEMP: 70.16,
                    API_MODE: 3,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 1,
                    API_HEAT_STAGE: 1,
                    API_HUMIDITY: 36,
                    API_UNITS: 1,
                    API_ERRORS: [],
                    API_AIR_DEMAND: 0,
                    API_FLOOR_DEMAND: 0,
                },
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 5,
                    API_NAME: "Dorm #2",
                    API_ON: 0,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19.5,
                    API_ROOM_TEMP: 20.5,
                    API_MODE: 3,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 1,
                    API_HEAT_STAGE: 1,
                    API_HUMIDITY: 40,
                    API_UNITS: 0,
                    API_ERRORS: [],
                    API_AIR_DEMAND: 0,
                    API_FLOOR_DEMAND: 0,
                },
            ]
        }
    ]
}


async def async_init_integration(
    hass: HomeAssistant,
):
    """Set up the Airzone integration in Home Assistant."""

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "aioairzone.localapi_device.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
