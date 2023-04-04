"""Test Notion diagnostics."""
from homeassistant.components.diagnostics import REDACTED
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
            "domain": "notion",
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
            "bridges": {
                "12345": {
                    "id": 12345,
                    "name": None,
                    "mode": "home",
                    "hardware_id": REDACTED,
                    "hardware_revision": 4,
                    "firmware_version": {
                        "wifi": "0.121.0",
                        "wifi_app": "3.3.0",
                        "silabs": "1.0.1",
                    },
                    "missing_at": None,
                    "created_at": "2019-04-30T01:43:50.497Z",
                    "updated_at": "2019-04-30T01:44:43.749Z",
                    "system_id": 12345,
                    "firmware": {
                        "wifi": "0.121.0",
                        "wifi_app": "3.3.0",
                        "silabs": "1.0.1",
                    },
                    "links": {"system": 12345},
                }
            },
            "sensors": {
                "123456": {
                    "id": 123456,
                    "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "user": {"id": 12345, "email": REDACTED},
                    "bridge": {"id": 12345, "hardware_id": REDACTED},
                    "last_bridge_hardware_id": REDACTED,
                    "name": "Bathroom Sensor",
                    "location_id": 123456,
                    "system_id": 12345,
                    "hardware_id": REDACTED,
                    "firmware_version": "1.1.2",
                    "hardware_revision": 5,
                    "device_key": REDACTED,
                    "encryption_key": True,
                    "installed_at": "2019-04-30T01:57:34.443Z",
                    "calibrated_at": "2019-04-30T01:57:35.651Z",
                    "last_reported_at": "2019-04-30T02:20:04.821Z",
                    "missing_at": None,
                    "updated_at": "2019-04-30T01:57:36.129Z",
                    "created_at": "2019-04-30T01:56:45.932Z",
                    "signal_strength": 5,
                    "links": {"location": 123456},
                    "lqi": 0,
                    "rssi": -46,
                    "surface_type": None,
                },
                "132462": {
                    "id": 132462,
                    "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "user": {"id": 12345, "email": REDACTED},
                    "bridge": {"id": 12345, "hardware_id": REDACTED},
                    "last_bridge_hardware_id": REDACTED,
                    "name": "Living Room Sensor",
                    "location_id": 123456,
                    "system_id": 12345,
                    "hardware_id": REDACTED,
                    "firmware_version": "1.1.2",
                    "hardware_revision": 5,
                    "device_key": REDACTED,
                    "encryption_key": True,
                    "installed_at": "2019-04-30T01:45:56.169Z",
                    "calibrated_at": "2019-04-30T01:46:06.256Z",
                    "last_reported_at": "2019-04-30T02:20:04.829Z",
                    "missing_at": None,
                    "updated_at": "2019-04-30T01:46:07.717Z",
                    "created_at": "2019-04-30T01:45:14.148Z",
                    "signal_strength": 5,
                    "links": {"location": 123456},
                    "lqi": 0,
                    "rssi": -30,
                    "surface_type": None,
                },
            },
            "tasks": {
                "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx": {
                    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "task_type": "low_battery",
                    "sensor_data": [],
                    "status": {
                        "insights": {
                            "primary": {
                                "from_state": None,
                                "to_state": "high",
                                "data_received_at": "2020-11-17T18:40:27.024Z",
                                "origin": {},
                            }
                        }
                    },
                    "created_at": "2020-11-17T18:40:27.024Z",
                    "updated_at": "2020-11-17T18:40:27.033Z",
                    "sensor_id": 525993,
                    "model_version": "4.1",
                    "configuration": {},
                    "links": {"sensor": 525993},
                }
            },
        },
    }
