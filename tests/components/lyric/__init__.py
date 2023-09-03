"""Tests for the Honeywell Lyric integration."""

from datetime import timedelta
import logging
from unittest.mock import PropertyMock, patch

from aiolyric import Lyric, LyricLocation, LyricPriority, LyricRoom

import homeassistant.components.lyric
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry


async def init_integration(hass: HomeAssistant, platform: str):
    """Set up the lyric integration in Home Assistant."""
    with (
        patch.object(
            Lyric, "locations", new_callable=PropertyMock(return_value=LOCATION_LIST)
        ),
        patch.object(
            Lyric,
            "locations_dict",
            new_callable=PropertyMock(return_value=LOCATION_DICT),
        ),
        patch.object(
            Lyric, "rooms_dict", new_callable=PropertyMock(return_value=ROOM_DICT)
        ),
    ):
        lyric = Lyric(None, "client_id")

        async def hass_async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
            await hass.config_entries.async_forward_entry_setups(entry, [platform])
            return True

        async def _async_update_data():
            return lyric

        setattr(
            homeassistant.components.lyric, "async_setup_entry", hass_async_setup_entry
        )

        entry = MockConfigEntry(domain=DOMAIN, data={})
        entry.add_to_hass(hass)

        coordinator = DataUpdateCoordinator(
            hass,
            logging.getLogger(__name__),
            name="any",
            update_method=_async_update_data,
            update_interval=timedelta(seconds=10000),
        )
        coordinator.data = lyric

        hass.data[DOMAIN] = {entry.entry_id: coordinator}

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED


LOCATION_ID = "1234567"
DEVICE_ID = "89C84637D2B2"  # Generated, fake MAC Addr

LOCATION_JSON_DATA = [
    {
        "locationID": LOCATION_ID,
        "name": "Home",
        "streetAddress": "",
        "city": "",
        "country": "US",
        "zipcode": "55555",
        "devices": [
            {
                "groups": [{"id": 0, "name": "default", "rooms": [0, 1, 2, 3, 4, 5]}],
                "displayedOutdoorHumidity": 55,
                "vacationHold": {"enabled": False},
                "currentSchedulePeriod": {"day": "Saturday", "period": "Wake"},
                "scheduleCapabilities": {
                    "availableScheduleTypes": [
                        "None",
                        "Geofenced",
                        "TimedNorthAmerica",
                    ],
                    "schedulableFan": True,
                },
                "scheduleType": {"scheduleType": "Timed", "scheduleSubType": "NA"},
                "inBuiltSensorState": {"roomId": 0, "roomName": "Hallway"},
                "scheduleStatus": "Resume",
                "allowedTimeIncrements": 15,
                "settings": {
                    "hardwareSettings": {"brightness": 0, "maxBrightness": 0},
                    "fan": {
                        "allowedModes": ["On", "Auto", "Circulate"],
                        "changeableValues": {"mode": "On"},
                    },
                    "temperatureMode": {"air": True},
                    "specialMode": {"autoChangeoverActive": True},
                    "devicePairingEnabled": True,
                },
                "deviceOsVersion": "RCHT1234WFW1999",
                "deviceClass": "Thermostat",
                "deviceType": "Thermostat",
                "deviceID": f"LCC-{DEVICE_ID}",
                "deviceInternalID": 1234567,
                "userDefinedDeviceName": "Hallway",
                "name": "Hallway",
                "isAlive": True,
                "isUpgrading": False,
                "isProvisioned": True,
                "macID": DEVICE_ID,
                "deviceSettings": {},
                "priorityType": "PickARoom",
                "service": {"mode": "Up"},
                "deviceRegistrationDate": "2022-07-24T22:09:57.84",
                "dataSyncStatus": "Completed",
                "deviceSerialNo": "11234ABC45647ADS",
                "units": "Fahrenheit",
                "indoorTemperature": 76,
                "outdoorTemperature": 85.6,
                "allowedModes": ["Heat", "Off", "Cool", "Auto"],
                "deadband": 0,
                "hasDualSetpointStatus": False,
                "minHeatSetpoint": 50,
                "maxHeatSetpoint": 90,
                "minCoolSetpoint": 50,
                "maxCoolSetpoint": 90,
                "changeableValues": {
                    "mode": "Auto",
                    "autoChangeoverActive": True,
                    "heatSetpoint": 69,
                    "coolSetpoint": 76,
                    "thermostatSetpointStatus": "NoHold",
                    "nextPeriodTime": "23:00:00",
                    "heatCoolMode": "Cool",
                },
                "operationStatus": {
                    "mode": "EquipmentOff",
                    "fanRequest": False,
                    "circulationFanRequest": False,
                },
                "indoorHumidity": 58,
                "indoorHumidityStatus": "Measured",
                "deviceModel": "T9-T10",
            }
        ],
        "users": [
            {
                "userID": 12345678,
                "username": "email@google.com",
                "firstname": "Bill",
                "lastname": "Williamson",
                "created": 1576889598,
                "deleted": -62135596800,
                "activated": True,
                "connectedHomeAccountExists": True,
                "locationRoleMapping": [
                    {
                        "locationID": LOCATION_ID,
                        "role": "Adult",
                        "locationName": "Home",
                        "status": 1,
                    }
                ],
                "isOptOut": "False",
                "isCurrentUser": True,
            }
        ],
        "timeZoneId": "Central",
        "timeZone": "Central Standard Time",
        "ianaTimeZone": "America/Chicago",
        "daylightSavingTimeEnabled": True,
        "geoFenceEnabled": False,
        "predictiveAIREnabled": False,
        "comfortLevel": 0,
        "geoFenceNotificationEnabled": False,
        "geoFenceNotificationTypeId": 13,
        "configuration": {
            "faceRecognition": {
                "enabled": False,
                "maxPersons": 2,
                "maxEtas": 2,
                "maxEtaPersons": 1,
                "schedules": [
                    {
                        "time": [{"start": "15:00:00", "end": "17:00:00"}],
                        "days": [
                            "Sunday",
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                            "Saturday",
                        ],
                    }
                ],
            }
        },
    }
]
LOCATION_LIST: list[LyricLocation] = [
    LyricLocation(None, location) for location in LOCATION_JSON_DATA or []
]
LOCATION_DICT: dict[str, LyricLocation] = {LOCATION_ID: LOCATION_LIST[0]}

PRIORITY_JSON_DATA = {
    "deviceId": DEVICE_ID,
    "status": "NoHold",
    "currentPriority": {
        "priorityType": "PickARoom",
        "selectedRooms": [0],
        "rooms": [
            {
                "id": 0,
                "roomName": "Hallway",
                "roomAvgTemp": 72.5,
                "roomAvgHumidity": 59,
                "overallMotion": False,
                "accessories": [
                    {
                        "id": 0,
                        "type": "Thermostat",
                        "excludeTemp": False,
                        "excludeMotion": False,
                        "temperature": 76.039,
                        "status": "Ok",
                        "detectMotion": False,
                    }
                ],
            },
            {
                "id": 1,
                "roomName": "Office",
                "roomAvgTemp": 76,
                "roomAvgHumidity": 57,
                "overallMotion": True,
                "accessories": [
                    {
                        "id": 1,
                        "type": "IndoorAirSensor",
                        "excludeTemp": False,
                        "excludeMotion": False,
                        "temperature": 76,
                        "status": "Ok",
                        "detectMotion": True,
                    }
                ],
            },
            {
                "id": 2,
                "roomName": "Master Bedroom",
                "roomAvgTemp": 73.12,
                "roomAvgHumidity": 58,
                "overallMotion": True,
                "accessories": [
                    {
                        "id": 2,
                        "type": "IndoorAirSensor",
                        "excludeTemp": False,
                        "excludeMotion": False,
                        "temperature": 76,
                        "status": "Ok",
                        "detectMotion": True,
                    }
                ],
            },
            {
                "id": 3,
                "roomName": "Library",
                "roomAvgTemp": 71,
                "roomAvgHumidity": 65,
                "overallMotion": True,
                "accessories": [
                    {
                        "id": 3,
                        "type": "IndoorAirSensor",
                        "excludeTemp": False,
                        "excludeMotion": False,
                        "temperature": 76,
                        "status": "Ok",
                        "detectMotion": True,
                    }
                ],
            },
            {
                "id": 4,
                "roomName": "Living Room",
                "roomAvgTemp": 79,
                "roomAvgHumidity": 63,
                "overallMotion": False,
                "accessories": [
                    {
                        "id": 4,
                        "type": "IndoorAirSensor",
                        "excludeTemp": False,
                        "excludeMotion": False,
                        "temperature": 76,
                        "status": "Ok",
                        "detectMotion": True,
                    }
                ],
            },
            {
                "id": 5,
                "roomName": "Family Room",
                "roomAvgTemp": 76.2,
                "roomAvgHumidity": 61,
                "overallMotion": False,
                "accessories": [
                    {
                        "id": 5,
                        "type": "IndoorAirSensor",
                        "excludeTemp": False,
                        "excludeMotion": False,
                        "temperature": 76,
                        "status": "Ok",
                        "detectMotion": True,
                    }
                ],
            },
        ],
    },
}

PRIOIRTY_DICT: dict[str, LyricPriority] = {DEVICE_ID: LyricPriority(PRIORITY_JSON_DATA)}

ROOM_DICT: dict[str, dict[int, LyricRoom]] = {
    DEVICE_ID: {
        0: PRIOIRTY_DICT[DEVICE_ID].currentPriority.rooms[0],
        1: PRIOIRTY_DICT[DEVICE_ID].currentPriority.rooms[1],
        2: PRIOIRTY_DICT[DEVICE_ID].currentPriority.rooms[2],
        3: PRIOIRTY_DICT[DEVICE_ID].currentPriority.rooms[3],
        4: PRIOIRTY_DICT[DEVICE_ID].currentPriority.rooms[4],
        5: PRIOIRTY_DICT[DEVICE_ID].currentPriority.rooms[5],
    }
}
