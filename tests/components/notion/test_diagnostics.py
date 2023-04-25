"""Test Notion diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.notion import DOMAIN
from homeassistant.core import HomeAssistant

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
            "domain": DOMAIN,
            "title": REDACTED,
            "data": {"username": REDACTED, "password": REDACTED},
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
        },
        "data": {
            "bridges": [
                {
                    "id": 12345,
                    "name": "Bridge 1",
                    "mode": "home",
                    "hardware_id": REDACTED,
                    "hardware_revision": 4,
                    "firmware_version": {
                        "silabs": "1.1.2",
                        "wifi": "0.121.0",
                        "wifi_app": "3.3.0",
                    },
                    "missing_at": None,
                    "created_at": "2019-06-27T00:18:44.337000+00:00",
                    "updated_at": "2023-03-19T03:20:16.061000+00:00",
                    "system_id": 11111,
                    "firmware": {
                        "silabs": "1.1.2",
                        "wifi": "0.121.0",
                        "wifi_app": "3.3.0",
                    },
                    "links": {"system": 11111},
                },
                {
                    "id": 67890,
                    "name": "Bridge 2",
                    "mode": "home",
                    "hardware_id": REDACTED,
                    "hardware_revision": 4,
                    "firmware_version": {
                        "silabs": "1.1.2",
                        "wifi": "0.121.0",
                        "wifi_app": "3.3.0",
                    },
                    "missing_at": None,
                    "created_at": "2019-04-30T01:43:50.497000+00:00",
                    "updated_at": "2023-01-02T19:09:58.251000+00:00",
                    "system_id": 11111,
                    "firmware": {
                        "silabs": "1.1.2",
                        "wifi": "0.121.0",
                        "wifi_app": "3.3.0",
                    },
                    "links": {"system": 11111},
                },
            ],
            "listeners": [
                {
                    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "listener_kind": {
                        "__type": "<enum 'ListenerKind'>",
                        "repr": "<ListenerKind.SMOKE: 7>",
                    },
                    "created_at": "2019-07-10T22:40:48.847000+00:00",
                    "device_type": "sensor",
                    "model_version": "3.1",
                    "sensor_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "status": {
                        "trigger_value": "no_alarm",
                        "data_received_at": "2019-06-28T22:12:49.516000+00:00",
                    },
                    "status_localized": {
                        "state": "No Sound",
                        "description": "Jun 28 at 4:12pm",
                    },
                    "insights": {
                        "primary": {
                            "origin": {"type": None, "id": None},
                            "value": "no_alarm",
                            "data_received_at": "2019-06-28T22:12:49.516000+00:00",
                        }
                    },
                    "configuration": {},
                    "pro_monitoring_status": "eligible",
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
                    "installed_at": "2019-06-28T22:12:51.209000+00:00",
                    "calibrated_at": "2023-03-07T19:51:56.838000+00:00",
                    "last_reported_at": "2023-04-19T18:09:40.479000+00:00",
                    "missing_at": None,
                    "updated_at": "2023-03-28T13:33:33.801000+00:00",
                    "created_at": "2019-06-28T22:12:20.256000+00:00",
                    "signal_strength": 4,
                    "firmware": {"status": "valid"},
                    "surface_type": None,
                }
            ],
        },
    }
