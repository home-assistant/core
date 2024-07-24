"""The tests for evohome."""

from typing import Final

TEST_USER_ACCOUNT: Final = {
    "userId": "2512649",
    "username": "user_2512649@gmail.com",
    "firstname": "John",
    "lastname": "Smith",
    "streetAddress": "1 Main Street",
    "city": "London",
    "postcode": "E1 1AA",
    "country": "UnitedKingdom",
    "language": "enGB",
}

TEST_INSTALL_INFO: Final = [
    {
        "locationInfo": {
            "locationId": "2738909",
            "name": "My Home",
            "streetAddress": "45 Main Crescent",
            "city": "London",
            "country": "UnitedKingdom",
            "postcode": "E1 2AA",
            "locationType": "Residential",
            "useDaylightSaveSwitching": True,
            "timeZone": {
                "timeZoneId": "GMTStandardTime",
                "displayName": "(UTC+00:00) Dublin, Edinburgh, Lisbon, London",
                "offsetMinutes": 0,
                "currentOffsetMinutes": 60,
                "supportsDaylightSaving": True,
            },
            "locationOwner": {
                "userId": "2263181",
                "username": "user_2263181@gmail.com",
                "firstname": "David",
                "lastname": "Smith",
            },
        },
        "gateways": [
            {
                "gatewayInfo": {
                    "gatewayId": "2499896",
                    "mac": "00D02DEE4E56",
                    "crc": "1234",
                    "isWiFi": False,
                },
                "temperatureControlSystems": [
                    {
                        "systemId": "3432522",
                        "modelType": "EvoTouch",
                        "zones": [
                            {
                                "zoneId": "3432521",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Dead Zone",
                                "zoneType": "RadiatorZone",
                            },
                            {
                                "zoneId": "3432576",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Main Room",
                                "zoneType": "RadiatorZone",
                            },
                            {
                                "zoneId": "3432577",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Front Room",
                                "zoneType": "RadiatorZone",
                            },
                            {
                                "zoneId": "3432578",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Kitchen",
                                "zoneType": "RadiatorZone",
                            },
                            {
                                "zoneId": "3432579",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Bathroom Dn",
                                "zoneType": "RadiatorZone",
                            },
                            {
                                "zoneId": "3432580",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Main Bedroom",
                                "zoneType": "RadiatorZone",
                            },
                            {
                                "zoneId": "3449703",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Kids Room",
                                "zoneType": "RadiatorZone",
                            },
                            {
                                "zoneId": "3449740",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Bathroom Up",
                                "zoneType": "RadiatorZone",
                            },
                            {
                                "zoneId": "3450733",
                                "modelType": "HeatingZone",
                                "setpointCapabilities": {
                                    "maxHeatSetpoint": 35.0,
                                    "minHeatSetpoint": 5.0,
                                    "valueResolution": 0.5,
                                    "canControlHeat": True,
                                    "canControlCool": False,
                                    "allowedSetpointModes": [
                                        "PermanentOverride",
                                        "FollowSchedule",
                                        "TemporaryOverride",
                                    ],
                                    "maxDuration": "1.00:00:00",
                                    "timingResolution": "00:10:00",
                                },
                                "scheduleCapabilities": {
                                    "maxSwitchpointsPerDay": 6,
                                    "minSwitchpointsPerDay": 1,
                                    "timingResolution": "00:10:00",
                                    "setpointValueResolution": 0.5,
                                },
                                "name": "Spare Room",
                                "zoneType": "RadiatorZone",
                            },
                        ],
                        "dhw": {
                            "dhwId": "3933910",
                            "dhwStateCapabilitiesResponse": {
                                "allowedStates": ["On", "Off"],
                                "allowedModes": [
                                    "FollowSchedule",
                                    "PermanentOverride",
                                    "TemporaryOverride",
                                ],
                                "maxDuration": "1.00:00:00",
                                "timingResolution": "00:10:00",
                            },
                            "scheduleCapabilitiesResponse": {
                                "maxSwitchpointsPerDay": 6,
                                "minSwitchpointsPerDay": 1,
                                "timingResolution": "00:10:00",
                            },
                        },
                        "allowedSystemModes": [
                            {
                                "systemMode": "HeatingOff",
                                "canBePermanent": True,
                                "canBeTemporary": False,
                            },
                            {
                                "systemMode": "Auto",
                                "canBePermanent": True,
                                "canBeTemporary": False,
                            },
                            {
                                "systemMode": "AutoWithReset",
                                "canBePermanent": True,
                                "canBeTemporary": False,
                            },
                            {
                                "systemMode": "AutoWithEco",
                                "canBePermanent": True,
                                "canBeTemporary": True,
                                "maxDuration": "1.00:00:00",
                                "timingResolution": "01:00:00",
                                "timingMode": "Duration",
                            },
                            {
                                "systemMode": "Away",
                                "canBePermanent": True,
                                "canBeTemporary": True,
                                "maxDuration": "99.00:00:00",
                                "timingResolution": "1.00:00:00",
                                "timingMode": "Period",
                            },
                            {
                                "systemMode": "DayOff",
                                "canBePermanent": True,
                                "canBeTemporary": True,
                                "maxDuration": "99.00:00:00",
                                "timingResolution": "1.00:00:00",
                                "timingMode": "Period",
                            },
                            {
                                "systemMode": "Custom",
                                "canBePermanent": True,
                                "canBeTemporary": True,
                                "maxDuration": "99.00:00:00",
                                "timingResolution": "1.00:00:00",
                                "timingMode": "Period",
                            },
                        ],
                    }
                ],
            }
        ],
    }
]

TEST_LOCN_STATUS: Final = {
    "locationId": "2738909",
    "gateways": [
        {
            "gatewayId": "2499896",
            "temperatureControlSystems": [
                {
                    "systemId": "3432522",
                    "zones": [
                        {
                            "zoneId": "3432521",
                            "temperatureStatus": {"isAvailable": False},
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 5.0,
                                "setpointMode": "PermanentOverride",
                            },
                            "name": "Dead Zone",
                        },
                        {
                            "zoneId": "3432576",
                            "temperatureStatus": {
                                "temperature": 19.0,
                                "isAvailable": True,
                            },
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 17.0,
                                "setpointMode": "FollowSchedule",
                            },
                            "name": "Main Room",
                        },
                        {
                            "zoneId": "3432577",
                            "temperatureStatus": {
                                "temperature": 19.0,
                                "isAvailable": True,
                            },
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 17.0,
                                "setpointMode": "FollowSchedule",
                            },
                            "name": "Front Room",
                        },
                        {
                            "zoneId": "3432578",
                            "temperatureStatus": {
                                "temperature": 20.0,
                                "isAvailable": True,
                            },
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 17.0,
                                "setpointMode": "FollowSchedule",
                            },
                            "name": "Kitchen",
                        },
                        {
                            "zoneId": "3432579",
                            "temperatureStatus": {
                                "temperature": 20.0,
                                "isAvailable": True,
                            },
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 16.0,
                                "setpointMode": "FollowSchedule",
                            },
                            "name": "Bathroom Dn",
                        },
                        {
                            "zoneId": "3432580",
                            "temperatureStatus": {
                                "temperature": 21.0,
                                "isAvailable": True,
                            },
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 16.0,
                                "setpointMode": "FollowSchedule",
                            },
                            "name": "Main Bedroom",
                        },
                        {
                            "zoneId": "3449703",
                            "temperatureStatus": {
                                "temperature": 19.5,
                                "isAvailable": True,
                            },
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 17.0,
                                "setpointMode": "FollowSchedule",
                            },
                            "name": "Kids Room",
                        },
                        {
                            "zoneId": "3449740",
                            "temperatureStatus": {
                                "temperature": 21.5,
                                "isAvailable": True,
                            },
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 16.5,
                                "setpointMode": "FollowSchedule",
                            },
                            "name": "Bathroom Up",
                        },
                        {
                            "zoneId": "3450733",
                            "temperatureStatus": {
                                "temperature": 19.5,
                                "isAvailable": True,
                            },
                            "activeFaults": [],
                            "setpointStatus": {
                                "targetHeatTemperature": 14.0,
                                "setpointMode": "PermanentOverride",
                            },
                            "name": "Spare Room",
                        },
                    ],
                    "dhw": {
                        "dhwId": "3933910",
                        "temperatureStatus": {"temperature": 23.0, "isAvailable": True},
                        "stateStatus": {"state": "Off", "mode": "PermanentOverride"},
                        "activeFaults": [],
                    },
                    "activeFaults": [],
                    "systemModeStatus": {"mode": "AutoWithEco", "isPermanent": True},
                }
            ],
            "activeFaults": [],
        }
    ],
}
