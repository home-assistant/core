"""Test Notion diagnostics."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.notion import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import ANY
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_config_entry,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 1,
            "minor_version": 1,
            "domain": DOMAIN,
            "title": REDACTED,
            "data": {
                "refresh_token": REDACTED,
                "user_uuid": REDACTED,
                "username": REDACTED,
            },
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
            "created_at": ANY,
            "modified_at": ANY,
            "discovery_keys": {},
            "subentries": [],
        },
        "data": {
            "bridges": [
                {
                    "id": 12345,
                    "name": "Laundry Closet",
                    "mode": "home",
                    "hardware_id": REDACTED,
                    "hardware_revision": 4,
                    "firmware_version": {
                        "wifi": "0.121.0",
                        "wifi_app": "3.3.0",
                        "silabs": "1.1.2",
                        "ti": None,
                    },
                    "missing_at": None,
                    "created_at": "2019-04-30T01:43:50.497000+00:00",
                    "updated_at": "2023-12-12T22:33:01.073000+00:00",
                    "system_id": 12345,
                    "firmware": {
                        "wifi": "0.121.0",
                        "wifi_app": "3.3.0",
                        "silabs": "1.1.2",
                        "ti": None,
                    },
                    "links": {"system": 12345},
                }
            ],
            "listeners": [
                {
                    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "definition_id": 24,
                    "created_at": "2019-06-17T03:29:45.722000+00:00",
                    "model_version": "1.0",
                    "sensor_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "status_localized": {
                        "state": "Idle",
                        "description": "Jun 18 at 12:17am",
                    },
                    "insights": {
                        "primary": {
                            "origin": {
                                "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                                "type": "Sensor",
                            },
                            "value": "idle",
                            "data_received_at": "2023-06-18T06:17:00.697000+00:00",
                        }
                    },
                    "configuration": {},
                    "pro_monitoring_status": "ineligible",
                    "device_type": "sensor",
                }
            ],
            "sensors": [
                {
                    "id": 123456,
                    "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "user": {"id": 12345, "email": REDACTED},
                    "bridge": {"id": 67890, "hardware_id": REDACTED},
                    "last_bridge_hardware_id": REDACTED,
                    "name": "Sensor 1",
                    "location_id": 123456,
                    "system_id": 12345,
                    "hardware_id": REDACTED,
                    "hardware_revision": 5,
                    "firmware_version": "1.1.2",
                    "device_key": REDACTED,
                    "encryption_key": True,
                    "installed_at": "2019-06-17T03:30:27.766000+00:00",
                    "calibrated_at": "2024-01-19T00:38:15.372000+00:00",
                    "last_reported_at": "2024-01-21T00:00:46.705000+00:00",
                    "missing_at": None,
                    "updated_at": "2024-01-19T00:38:16.856000+00:00",
                    "created_at": "2019-06-17T03:29:45.506000+00:00",
                    "signal_strength": 4,
                    "firmware": {"status": "valid"},
                    "surface_type": None,
                }
            ],
            "user_preferences": {
                "user_id": REDACTED,
                "military_time_enabled": False,
                "celsius_enabled": False,
                "disconnect_alerts_enabled": True,
                "home_away_alerts_enabled": False,
                "battery_alerts_enabled": True,
            },
        },
    }
