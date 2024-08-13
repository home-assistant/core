"""Tests for Ecobee integration."""

GENERIC_THERMOSTAT_INFO = {
    "identifier": 8675309,
    "name": "ecobee",
    "modelNumber": "athenaSmart",
    "program": {
        "climates": [
            {"name": "Climate1", "climateRef": "c1"},
            {"name": "Climate2", "climateRef": "c2"},
        ],
        "currentClimateRef": "c1",
    },
    "runtime": {
        "connected": True,
        "actualTemperature": 300,
        "actualHumidity": 15,
        "desiredHeat": 400,
        "desiredCool": 200,
        "desiredFanMode": "on",
        "desiredHumidity": 40,
    },
    "settings": {
        "hvacMode": "auto",
        "heatStages": 1,
        "coolStages": 1,
        "fanMinOnTime": 10,
        "heatCoolMinDelta": 50,
        "holdAction": "nextTransition",
        "hasHumidifier": False,
        "humidifierMode": "manual",
        "humidity": "30",
        "ventilatorType": "none",
    },
    "equipmentStatus": "fan",
    "events": [
        {
            "name": "Event1",
            "running": True,
            "type": "hold",
            "holdClimateRef": "away",
            "startDate": "2022-02-02",
            "startTime": "11:00:00",
            "endDate": "2022-01-01",
            "endTime": "10:00:00",
        }
    ],
    "remoteSensors": [
        {
            "id": "rs:100",
            "name": "Remote Sensor 1",
            "type": "ecobee3_remote_sensor",
            "code": "WKRP",
            "inUse": False,
            "capability": [
                {"id": "1", "type": "temperature", "value": "782"},
                {"id": "2", "type": "occupancy", "value": "false"},
            ],
        }
    ],
}


GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP = {
    "identifier": 8675309,
    "name": "ecobee",
    "modelNumber": "athenaSmart",
    "utcTime": "2022-01-01 10:00:00",
    "thermostatTime": "2022-01-01 6:00:00",
    "location": {"timeZone": "America/Toronto"},
    "program": {
        "climates": [
            {"name": "Climate1", "climateRef": "c1"},
            {"name": "Climate2", "climateRef": "c2"},
        ],
        "currentClimateRef": "c1",
    },
    "runtime": {
        "connected": True,
        "actualTemperature": 300,
        "actualHumidity": 15,
        "desiredHeat": 400,
        "desiredCool": 200,
        "desiredFanMode": "on",
        "desiredHumidity": 40,
    },
    "settings": {
        "hvacMode": "auto",
        "heatStages": 1,
        "coolStages": 1,
        "fanMinOnTime": 10,
        "heatCoolMinDelta": 50,
        "holdAction": "nextTransition",
        "hasHumidifier": False,
        "humidifierMode": "manual",
        "humidity": "30",
        "hasHeatPump": True,
        "ventilatorType": "hrv",
        "ventilatorOffDateTime": "2022-01-01 6:00:00",
    },
    "equipmentStatus": "fan",
    "events": [
        {
            "name": "Event1",
            "running": True,
            "type": "hold",
            "holdClimateRef": "away",
            "startDate": "2022-02-02",
            "startTime": "11:00:00",
            "endDate": "2022-01-01",
            "endTime": "10:00:00",
        }
    ],
    "remoteSensors": [
        {
            "id": "rs:100",
            "name": "Remote Sensor 1",
            "type": "ecobee3_remote_sensor",
            "code": "WKRP",
            "inUse": False,
            "capability": [
                {"id": "1", "type": "temperature", "value": "782"},
                {"id": "2", "type": "occupancy", "value": "false"},
            ],
        }
    ],
}
