"""Test Schlage diagnostics."""

from unittest.mock import Mock

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import MockSchlageConfigEntry

# Lock.get_diagnostics() output for the wifi_lock_json fixture in pyschlage's
# own tests, generated with pyschlage 2026.11.0.
LOCK_DIAGNOSTICS = {
    "CAT": "<REDACTED>",
    "SAT": "<REDACTED>",
    "attributes": {
        "CAT": "<REDACTED>",
        "SAT": "<REDACTED>",
        "accessCodeLength": 4,
        "actAlarmBuzzerEnabled": 0,
        "actAlarmState": 0,
        "actuationCurrentMax": 226,
        "alarmSelection": 0,
        "alarmSensitivity": 0,
        "alarmState": 0,
        "autoLockTime": 0,
        "batteryChangeDate": 1669017530,
        "batteryLevel": 95,
        "batteryLowState": 0,
        "batterySaverConfig": {"activePeriod": [], "enabled": 0},
        "batterySaverState": 0,
        "beeperEnabled": 1,
        "bleFirmwareVersion": "0118.000103.015",
        "diagnostics": {
            "currentVoltage": 5319,
            "filterVoltage": 5319,
            "noLoadVoltage": 5319,
            "someOtherReading": "<REDACTED>",
        },
        "firmwareUpdate": {"status": {"additionalInfo": None, "updateStatus": None}},
        "homePosCurrentMax": 153,
        "keypadFirmwareVersion": "03.00.00250052",
        "lockAndLeaveEnabled": 1,
        "lockState": 1,
        "lockStateMetadata": {
            "UUID": "<REDACTED>",
            "actionType": "periodicDeepQuery",
            "clientId": "<REDACTED>",
            "name": "<REDACTED>",
        },
        "macAddress": "<REDACTED>",
        "mainFirmwareVersion": "10.00.00264232",
        "mode": 2,
        "modelName": "__model_name__",
        "periodicDeepQueryTimeSetting": 60,
        "psPollEnabled": 1,
        "serialNumber": "<REDACTED>",
        "timezone": -20,
        "wifiFirmwareVersion": "03.15.00.01",
        "wifiRssi": -42,
    },
    "connected": True,
    "connectivityUpdated": "2022-12-04T20:58:22.000Z",
    "created": "2020-04-05T21:53:11.000Z",
    "deviceId": "<REDACTED>",
    "devicetypeId": "be489wifi",
    "lastUpdated": "2022-12-04T20:58:22.000Z",
    "macAddress": "<REDACTED>",
    "modelName": "__model_name__",
    "name": "Door Lock",
    "physicalId": "<REDACTED>",
    "relatedDevices": ["<REDACTED>"],
    "role": "owner",
    "serialNumber": "<REDACTED>",
    "timezone": -20,
    "users": ["<REDACTED>"],
}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_lock: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Schlage diagnostics."""
    mock_lock.get_diagnostics.return_value = LOCK_DIAGNOSTICS
    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_added_config_entry
    )
    assert diag == snapshot
