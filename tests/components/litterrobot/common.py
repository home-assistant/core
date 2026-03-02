"""Common utils for Litter-Robot tests."""

from homeassistant.components.litterrobot import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

CONFIG = {DOMAIN: {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"}}

ACCOUNT_USER_ID = "1234567"

ROBOT_NAME = "Test"
ROBOT_5_DATA = {
    "name": ROBOT_NAME,
    "serial": "LR5C010001",
    "type": "LR5",
    "timezone": "America/New_York",
    "powerStatus": "AC",
    "setupDateTime": "2022-08-28T17:01:12.644Z",
    "nextFilterReplacementDate": "2023-02-28T17:01:12.644Z",
    "state": {
        "odometerCleanCycles": 158,
        "odometerEmptyCycles": 1,
        "odometerFilterCycles": 0,
        "odometerPowerCycles": 8,
        "lastResetOdometerCleanCycles": 42,
        "DFINumberOfCycles": 104,
        "dfiFullCounter": 3,
        "catDetect": "CAT_DETECT_CLEAR",
        "isBonnetRemoved": False,
        "isDrawerRemoved": False,
        "isDrawerFull": False,
        "isLaserDirty": False,
        "isOnline": True,
        "isHopperInstalled": True,
        "isSleeping": False,
        "isNightLightOn": False,
        "isFirmwareUpdating": False,
        "isGasSensorFaultDetected": False,
        "isUsbFaultDetected": False,
        "weightSensor": 1200.0,
        "globeMotorFaultStatus": "FAULT_CLEAR",
        "globeMotorRetractFaultStatus": "FAULT_CLEAR",
        "pinchStatus": "CLEAR",
        "lastSeen": "2022-09-17T12:06:37.884Z",
        "setupDateTime": "2022-08-28T17:01:12.644Z",
        "firmwareVersions": {
            "mcuVersion": "10512.2560.2.53",
            "wifiVersion": "1.1.50",
        },
        "firmwareUpdateStatus": "NONE",
        "litterLevelPercent": 70.0,
        "globeLitterLevel": 460,
        "globeLitterLevelIndicator": "OPTIMAL",
        "robotState": "StRobotIdle",
        "displayCode": "DcModeIdle",
        "powerStatus": "AC",
        "wifiRssi": -53.0,
        "scoopsSaved": 3769,
    },
    "litterRobotSettings": {
        "cycleDelay": 15,
        "isSmartWeightEnabled": True,
    },
    "nightLightSettings": {
        "brightness": 50,
        "color": "#FFFFFF",
        "mode": "Auto",
    },
    "panelSettings": {
        "displayIntensity": "Medium",
        "isKeypadLocked": False,
    },
    "soundSettings": {
        "volume": 75,
    },
    "sleepSchedules": [
        {"dayOfWeek": 0, "isEnabled": True, "sleepTime": 1320, "wakeTime": 420},
        {"dayOfWeek": 1, "isEnabled": True, "sleepTime": 1320, "wakeTime": 420},
        {"dayOfWeek": 2, "isEnabled": True, "sleepTime": 1320, "wakeTime": 420},
        {"dayOfWeek": 3, "isEnabled": True, "sleepTime": 1320, "wakeTime": 420},
        {"dayOfWeek": 4, "isEnabled": True, "sleepTime": 1320, "wakeTime": 420},
        {"dayOfWeek": 5, "isEnabled": False, "sleepTime": 1380, "wakeTime": 480},
        {"dayOfWeek": 6, "isEnabled": False, "sleepTime": 1380, "wakeTime": 480},
    ],
}
PET_DATA = {
    "petId": "PET-123",
    "userId": "1234567",
    "createdAt": "2023-04-27T23:26:49.813Z",
    "name": "Kitty",
    "type": "CAT",
    "gender": "FEMALE",
    "lastWeightReading": 9.1,
    "breeds": ["sphynx"],
    "weightHistory": [
        {"weight": 6.48, "timestamp": "2025-06-13T16:12:36"},
        {"weight": 6.6, "timestamp": "2025-06-14T03:52:00"},
        {"weight": 6.59, "timestamp": "2025-06-14T17:20:32"},
        {"weight": 6.5, "timestamp": "2025-06-14T19:22:48"},
        {"weight": 6.35, "timestamp": "2025-06-15T03:12:15"},
        {"weight": 6.45, "timestamp": "2025-06-15T15:27:21"},
        {"weight": 6.25, "timestamp": "2025-06-15T15:29:26"},
    ],
}

ROBOT_5_PRO_DATA = {
    **ROBOT_5_DATA,
    "serial": "LR5P010001",
    "type": "LR5_PRO",
    "name": ROBOT_NAME,
    "state": {
        **ROBOT_5_DATA["state"],
        "serial": "LR5P010001",
        "type": "LR5_PRO",
    },
    "cameraMetadata": {
        "deviceId": "68f5f44bba1544a7cc8697c2",
        "serialNumber": "E0510076020EBFV",
        "spaceId": "69261e737e1f43011f75b804",
    },
    "soundSettings": {
        "volume": 50,
        "cameraAudioEnabled": False,
    },
}

VACUUM_ENTITY_ID = "vacuum.test_litter_box"
