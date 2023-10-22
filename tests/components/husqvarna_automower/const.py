"""Helpers for testing Husqvarana Automower."""

MWR_ONE_ID = "c7233734-b219-4287-a173-08e3643f89f0"
MWR_ONE_IDX = 0
MWR_TWO_ID = "1c7aec7b-06ff-462e-b307-7c6ae4469047"
MWR_TWO_IDX = 1


MOWER_ONE_SESSION_DATA = {
    "type": "mower",
    "id": MWR_ONE_ID,
    "attributes": {
        "system": {
            "name": "Test Mower 1",
            "model": "450XH-TEST",
            "serialNumber": 123,
        },
        "battery": {"batteryPercent": 100},
        "capabilities": {
            "headlights": True,
            "workAreas": False,
            "position": True,
            "stayOutZones": False,
        },
        "mower": {
            "mode": "MAIN_AREA",
            "activity": "PARKED_IN_CS",
            "state": "RESTRICTED",
            "errorCode": 0,
            "errorCodeTimestamp": 0,
        },
        "calendar": {
            "tasks": [
                {
                    "start": 1140,
                    "duration": 300,
                    "monday": True,
                    "tuesday": False,
                    "wednesday": True,
                    "thursday": False,
                    "friday": True,
                    "saturday": False,
                    "sunday": False,
                },
                {
                    "start": 0,
                    "duration": 480,
                    "monday": False,
                    "tuesday": True,
                    "wednesday": False,
                    "thursday": True,
                    "friday": False,
                    "saturday": True,
                    "sunday": False,
                },
            ]
        },
        "planner": {
            "nextStartTimestamp": 1685991600000,
            "override": {"action": "NOT_ACTIVE"},
            "restrictedReason": "WEEK_SCHEDULE",
        },
        "metadata": {"connected": True, "statusTimestamp": 1697669932683},
        "positions": [
            {"latitude": 35.5402913, "longitude": -82.5527055},
            {"latitude": 35.5407693, "longitude": -82.5521503},
            {"latitude": 35.5403241, "longitude": -82.5522924},
            {"latitude": 35.5406973, "longitude": -82.5518579},
            {"latitude": 35.5404659, "longitude": -82.5516567},
            {"latitude": 35.5406318, "longitude": -82.5515709},
            {"latitude": 35.5402477, "longitude": -82.5519437},
            {"latitude": 35.5403503, "longitude": -82.5516889},
            {"latitude": 35.5401429, "longitude": -82.551536},
            {"latitude": 35.5405489, "longitude": -82.5512195},
            {"latitude": 35.5404005, "longitude": -82.5512115},
            {"latitude": 35.5405969, "longitude": -82.551418},
            {"latitude": 35.5403437, "longitude": -82.5523917},
            {"latitude": 35.5403481, "longitude": -82.5520054},
        ],
        "cuttingHeight": 4,
        "headlight": {"mode": "EVENING_ONLY"},
        "statistics": {
            "numberOfChargingCycles": 1380,
            "numberOfCollisions": 11396,
            "totalChargingTime": 4334400,
            "totalCuttingTime": 4194000,
            "totalDriveDistance": 1780272,
            "totalRunningTime": 4564800,
            "totalSearchingTime": 370800,
        },
    },
}

MOWER_TWO_SESSION_DATA = {
    "attributes": {
        "system": {
            "name": "Test Mower 2",
            "model": "450XH-TEST",
        },
        "metadata": {"connected": True, "statusTimestamp": 1685899526195},
        "calendar": {
            "tasks": [
                {
                    "start": 1140,
                    "duration": 300,
                    "monday": True,
                    "tuesday": False,
                    "wednesday": True,
                    "thursday": False,
                    "friday": True,
                    "saturday": False,
                    "sunday": False,
                },
                {
                    "start": 0,
                    "duration": 480,
                    "monday": False,
                    "tuesday": True,
                    "wednesday": False,
                    "thursday": True,
                    "friday": False,
                    "saturday": True,
                    "sunday": False,
                },
            ]
        },
        "planner": {
            "nextStartTimestamp": 1685991600000,
            "override": {"action": None},
            "restrictedReason": "WEEK_SCHEDULE",
        },
        "positions": [
            {"latitude": 35.5409916, "longitude": -82.5525433},
            {"latitude": 35.5408149, "longitude": -82.5523743},
            {"latitude": 35.5402976, "longitude": -82.5521544},
            {"latitude": 35.5406534, "longitude": -82.5516823},
            {"latitude": 35.5404788, "longitude": -82.5516287},
            {"latitude": 35.5406053, "longitude": -82.5514785},
            {"latitude": 35.5402692, "longitude": -82.5520417},
            {"latitude": 35.5403369, "longitude": -82.5516716},
            {"latitude": 35.5401448, "longitude": -82.5515697},
            {"latitude": 35.5402605, "longitude": -82.5512907},
            {"latitude": 35.5405551, "longitude": -82.5512532},
            {"latitude": 35.5404504, "longitude": -82.5514329},
        ],
        "battery": {"batteryPercent": 100},
        "mower": {
            "mode": "MAIN_AREA",
            "activity": "PARKED_IN_CS",
            "state": "RESTRICTED",
            "errorCode": 0,
            "errorCodeTimestamp": 0,
        },
        "statistics": {
            "numberOfChargingCycles": 231,
            "numberOfCollisions": 48728,
            "totalChargingTime": 813600,
            "totalCuttingTime": 3945600,
            "totalRunningTime": 4078800,
            "totalSearchingTime": 133200,
        },
        "cuttingHeight": 4,
        "headlight": {"mode": "EVENING_ONLY"},
    },
    "id": MWR_TWO_ID,
    "type": "mower",
}

AUTOMOWER_ERROR_SESSION_DATA = {
    "errors": [
        {
            "id": MWR_ONE_ID,
            "status": "403",
            "code": "invalid.credentials",
            "title": "Invalid credentials",
            "detail": "The supplied credentials are invalid.",
        }
    ]
}

# Single Mower Options
AUTOMER_SM_CONFIG = {
    MWR_ONE_ID: {},
}

# Dual Mower Options
AUTOMER_DM_CONFIG = {
    MWR_ONE_ID: {},
    MWR_TWO_ID: {},
}

AUTOMOWER_SM_SESSION_DATA = {
    "data": [MOWER_ONE_SESSION_DATA],
}

AUTOMOWER_DM_SESSION_DATA = {
    "data": [MOWER_ONE_SESSION_DATA, MOWER_TWO_SESSION_DATA],
}

AUTOMOWER_CONFIG_DATA = {
    "auth_implementation": "husqvarna_automower_433e5fdf_5129_452c_ba7f_fadce3213042",
    "token": {
        "access_token": "f8f1983d-d88a-4ef1-91ab-af54fefaa9d0",
        "scope": "iam:read amc:api",
        "expires_in": 86399,
        "refresh_token": "ab152f21-811b-4417-a75f-4c8fe518644c",
        "provider": "husqvarna",
        "user_id": "d582fe49-80a5-417b-bf97-29ce20818712",
        "token_type": "Bearer",
        "expires_at": 1685908387.3688,
    },
}

AUTOMOWER_CONFIG_DATA_BAD_SCOPE = {
    "auth_implementation": "husqvarna_automower_433e5fdf_5129_452c_ba7f_fadce3213042",
    "token": {
        "access_token": "f8f1983d-d88a-4ef1-91ab-af54fefaa9d0",
        "scope": "iam:read",
        "expires_in": 86399,
        "refresh_token": "ab152f21-811b-4417-a75f-4c8fe518644c",
        "provider": "husqvarna",
        "user_id": "d582fe49-80a5-417b-bf97-29ce20818712",
        "token_type": "Bearer",
        "expires_at": 1685908387.3688,
    },
}
