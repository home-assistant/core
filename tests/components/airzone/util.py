"""Tests for the Airzone integration."""

from unittest.mock import patch

from aioairzone.const import (
    API_AIR_DEMAND,
    API_COLD_ANGLE,
    API_COLD_STAGE,
    API_COLD_STAGES,
    API_DATA,
    API_ERRORS,
    API_FLOOR_DEMAND,
    API_HEAT_ANGLE,
    API_HEAT_STAGE,
    API_HEAT_STAGES,
    API_HUMIDITY,
    API_MAC,
    API_MAX_TEMP,
    API_MIN_TEMP,
    API_MODE,
    API_MODES,
    API_NAME,
    API_ON,
    API_POWER,
    API_ROOM_TEMP,
    API_SET_POINT,
    API_SLEEP,
    API_SYSTEM_FIRMWARE,
    API_SYSTEM_ID,
    API_SYSTEM_TYPE,
    API_SYSTEMS,
    API_THERMOS_FIRMWARE,
    API_THERMOS_RADIO,
    API_THERMOS_TYPE,
    API_UNITS,
    API_VERSION,
    API_WIFI_CHANNEL,
    API_WIFI_RSSI,
    API_ZONE_ID,
)

from homeassistant.components.airzone import DOMAIN
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 3000,
}

CONFIG_ID1 = {
    **CONFIG,
    CONF_ID: 1,
}

HVAC_MOCK = {
    API_SYSTEMS: [
        {
            API_DATA: [
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 1,
                    API_NAME: "Salon",
                    API_THERMOS_TYPE: 2,
                    API_THERMOS_FIRMWARE: "3.51",
                    API_THERMOS_RADIO: 0,
                    API_ON: 0,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19.1,
                    API_ROOM_TEMP: 19.6,
                    API_SLEEP: 0,
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
                    API_HEAT_ANGLE: 0,
                    API_COLD_ANGLE: 0,
                },
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 2,
                    API_NAME: "Dorm Ppal",
                    API_THERMOS_TYPE: 4,
                    API_THERMOS_FIRMWARE: "3.33",
                    API_THERMOS_RADIO: 1,
                    API_ON: 1,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19.2,
                    API_ROOM_TEMP: 21.1,
                    API_SLEEP: 30,
                    API_MODE: 3,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 3,
                    API_HEAT_STAGE: 3,
                    API_HUMIDITY: 39,
                    API_UNITS: 0,
                    API_ERRORS: [],
                    API_AIR_DEMAND: 1,
                    API_FLOOR_DEMAND: 1,
                    API_HEAT_ANGLE: 1,
                    API_COLD_ANGLE: 2,
                },
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 3,
                    API_NAME: "Dorm #1",
                    API_THERMOS_TYPE: 4,
                    API_THERMOS_FIRMWARE: "3.33",
                    API_THERMOS_RADIO: 1,
                    API_ON: 1,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19.3,
                    API_ROOM_TEMP: 20.8,
                    API_SLEEP: 0,
                    API_MODE: 3,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 2,
                    API_HEAT_STAGE: 2,
                    API_HUMIDITY: 35,
                    API_UNITS: 0,
                    API_ERRORS: [],
                    API_AIR_DEMAND: 0,
                    API_FLOOR_DEMAND: 0,
                    API_HEAT_ANGLE: 0,
                    API_COLD_ANGLE: 0,
                },
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 4,
                    API_NAME: "Despacho",
                    API_THERMOS_TYPE: 4,
                    API_THERMOS_FIRMWARE: "3.33",
                    API_THERMOS_RADIO: 1,
                    API_ON: 0,
                    API_MAX_TEMP: 86,
                    API_MIN_TEMP: 59,
                    API_SET_POINT: 66.92,
                    API_ROOM_TEMP: 70.16,
                    API_SLEEP: 0,
                    API_MODE: 3,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 1,
                    API_HEAT_STAGE: 1,
                    API_HUMIDITY: 36,
                    API_UNITS: 1,
                    API_ERRORS: [
                        {
                            "Zone": "Low battery",
                        },
                    ],
                    API_AIR_DEMAND: 0,
                    API_FLOOR_DEMAND: 0,
                    API_HEAT_ANGLE: 0,
                    API_COLD_ANGLE: 0,
                },
                {
                    API_SYSTEM_ID: 1,
                    API_ZONE_ID: 5,
                    API_NAME: "Dorm #2",
                    API_THERMOS_TYPE: 4,
                    API_THERMOS_FIRMWARE: "3.33",
                    API_THERMOS_RADIO: 1,
                    API_ON: 0,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19.5,
                    API_ROOM_TEMP: 20.5,
                    API_SLEEP: 0,
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
                    API_HEAT_ANGLE: 0,
                    API_COLD_ANGLE: 0,
                },
            ]
        },
        {
            API_DATA: [
                {
                    API_SYSTEM_ID: 2,
                    API_ZONE_ID: 1,
                    API_ON: 0,
                    API_MAX_TEMP: 30,
                    API_MIN_TEMP: 15,
                    API_SET_POINT: 19,
                    API_ROOM_TEMP: 22.299999,
                    API_COLD_STAGES: 1,
                    API_COLD_STAGE: 1,
                    API_HEAT_STAGES: 1,
                    API_HEAT_STAGE: 1,
                    API_HUMIDITY: 62,
                    API_UNITS: 0,
                    API_ERRORS: [],
                },
            ]
        },
    ]
}

HVAC_SYSTEMS_MOCK = {
    API_SYSTEMS: [
        {
            API_SYSTEM_ID: 1,
            API_POWER: 0,
            API_SYSTEM_FIRMWARE: "3.31",
            API_SYSTEM_TYPE: 1,
        }
    ]
}

HVAC_VERSION_MOCK = {
    API_VERSION: "1.62",
}

HVAC_WEBSERVER_MOCK = {
    API_MAC: "11:22:33:44:55:66",
    API_WIFI_CHANNEL: 6,
    API_WIFI_RSSI: -42,
}


async def async_init_integration(
    hass: HomeAssistant,
) -> None:
    """Set up the Airzone integration in Home Assistant."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
        unique_id="airzone_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
        return_value=HVAC_SYSTEMS_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
        return_value=HVAC_WEBSERVER_MOCK,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
