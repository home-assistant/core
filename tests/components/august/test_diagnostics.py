"""Test august diagnostics."""
from homeassistant.core import HomeAssistant

from .mocks import (
    _create_august_api_with_devices,
    _mock_doorbell_from_fixture,
    _mock_lock_from_fixture,
)

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test generating diagnostics for a config entry."""
    lock_one = await _mock_lock_from_fixture(
        hass, "get_lock.online_with_doorsense.json"
    )
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")

    entry, _ = await _create_august_api_with_devices(hass, [lock_one, doorbell_one])
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == {
        "doorbells": {
            "K98GiDT45GUL": {
                "HouseID": "**REDACTED**",
                "LockID": "BBBB1F5F11114C24CCCC97571DD6AAAA",
                "appID": "august-iphone",
                "caps": ["reconnect"],
                "createdAt": "2016-11-26T22:27:11.176Z",
                "doorbellID": "K98GiDT45GUL",
                "doorbellServerURL": "https://doorbells.august.com",
                "dvrSubscriptionSetupDone": True,
                "firmwareVersion": "2.3.0-RC153+201711151527",
                "installDate": "2016-11-26T22:27:11.176Z",
                "installUserID": "**REDACTED**",
                "name": "Front Door",
                "pubsubChannel": "**REDACTED**",
                "recentImage": "**REDACTED**",
                "serialNumber": "tBXZR0Z35E",
                "settings": {
                    "ABREnabled": True,
                    "IREnabled": True,
                    "IVAEnabled": False,
                    "JPGQuality": 70,
                    "batteryLowThreshold": 3.1,
                    "batteryRun": False,
                    "batteryUseThreshold": 3.4,
                    "bitrateCeiling": 512000,
                    "buttonpush_notifications": True,
                    "debug": False,
                    "directLink": True,
                    "initialBitrate": 384000,
                    "irConfiguration": 8448272,
                    "keepEncoderRunning": True,
                    "micVolume": 100,
                    "minACNoScaling": 40,
                    "motion_notifications": True,
                    "notify_when_offline": True,
                    "overlayEnabled": True,
                    "ringSoundEnabled": True,
                    "speakerVolume": 92,
                    "turnOffCamera": False,
                    "videoResolution": "640x480",
                },
                "status": "doorbell_call_status_online",
                "status_timestamp": 1512811834532,
                "telemetry": {
                    "BSSID": "88:ee:00:dd:aa:11",
                    "SSID": "foo_ssid",
                    "ac_in": 23.856874,
                    "battery": 4.061763,
                    "battery_soc": 96,
                    "battery_soh": 95,
                    "date": "2017-12-10 08:05:12",
                    "doorbell_low_battery": False,
                    "ip_addr": "10.0.1.11",
                    "link_quality": 54,
                    "load_average": "0.50 0.47 0.35 1/154 9345",
                    "signal_level": -56,
                    "steady_ac_in": 22.196405,
                    "temperature": 28.25,
                    "updated_at": "2017-12-10T08:05:13.650Z",
                    "uptime": "16168.75 13830.49",
                    "wifi_freq": 5745,
                },
                "updatedAt": "2017-12-10T08:05:13.650Z",
            }
        },
        "locks": {
            "online_with_doorsense": {
                "Bridge": {
                    "_id": "bridgeid",
                    "deviceModel": "august-connect",
                    "firmwareVersion": "2.2.1",
                    "hyperBridge": True,
                    "mfgBridgeID": "C5WY200WSH",
                    "operative": True,
                    "status": {
                        "current": "online",
                        "lastOffline": "2000-00-00T00:00:00.447Z",
                        "lastOnline": "2000-00-00T00:00:00.447Z",
                        "updated": "2000-00-00T00:00:00.447Z",
                    },
                },
                "Calibrated": False,
                "Created": "2000-00-00T00:00:00.447Z",
                "HouseID": "**REDACTED**",
                "HouseName": "Test",
                "LockID": "online_with_doorsense",
                "LockName": "Online door with doorsense",
                "LockStatus": {
                    "dateTime": "2017-12-10T04:48:30.272Z",
                    "doorState": "open",
                    "isLockStatusChanged": False,
                    "status": "locked",
                    "valid": True,
                },
                "SerialNumber": "XY",
                "Type": 1001,
                "Updated": "2000-00-00T00:00:00.447Z",
                "battery": 0.922,
                "currentFirmwareVersion": "undefined-4.3.0-1.8.14",
                "homeKitEnabled": True,
                "hostLockInfo": {
                    "manufacturer": "yale",
                    "productID": 1536,
                    "productTypeID": 32770,
                    "serialNumber": "ABC",
                },
                "isGalileo": False,
                "macAddress": "12:22",
                "pins": "**REDACTED**",
                "pubsubChannel": "**REDACTED**",
                "skuNumber": "AUG-MD01",
                "supportsEntryCodes": True,
                "timeZone": "Pacific/Hawaii",
                "zWaveEnabled": False,
            }
        },
        "brand": "august",
    }
