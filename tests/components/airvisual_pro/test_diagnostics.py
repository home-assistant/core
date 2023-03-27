"""Test AirVisual Pro diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_airvisual_pro,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 1,
            "domain": "airvisual_pro",
            "title": "Mock Title",
            "data": {"ip_address": "192.168.1.101", "password": REDACTED},
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": "XXXXXXX",
            "disabled_by": None,
        },
        "data": {
            "date_and_time": {
                "date": "2022/10/06",
                "time": "16:00:44",
                "timestamp": "1665072044",
            },
            "measurements": {
                "co2": "472",
                "humidity": "57",
                "pm0_1": "0",
                "pm1_0": "0",
                "aqi_cn": "0",
                "aqi_us": "0",
                "pm2_5": "0",
                "temperature_C": "23.0",
                "temperature_F": "73.4",
                "voc": "-1",
            },
            "serial_number": REDACTED,
            "settings": {
                "follow_mode": "station",
                "followed_station": "0",
                "is_aqi_usa": True,
                "is_concentration_showed": True,
                "is_indoor": True,
                "is_lcd_on": True,
                "is_network_time": True,
                "is_temperature_celsius": False,
                "language": "en-US",
                "lcd_brightness": 80,
                "node_name": "Office",
                "power_saving": {
                    "2slots": [
                        {"hour_off": 9, "hour_on": 7},
                        {"hour_off": 22, "hour_on": 18},
                    ],
                    "mode": "yes",
                    "running_time": 99,
                    "yes": [{"hour": 8, "minute": 0}, {"hour": 21, "minute": 0}],
                },
                "sensor_mode": {"custom_mode_interval": 3, "mode": 1},
                "speed_unit": "mph",
                "timezone": "America/New York",
                "tvoc_unit": "ppb",
            },
            "status": {
                "app_version": "1.1826",
                "battery": 100,
                "datetime": 1665072044,
                "device_name": "AIRVISUAL-XXXXXXX",
                "ip_address": "192.168.1.101",
                "mac_address": REDACTED,
                "model": 20,
                "sensor_life": {"pm2_5": 1567924345130},
                "sensor_pm25_serial": "00000005050224011145",
                "sync_time": 250000,
                "system_version": "KBG63F84",
                "used_memory": 3,
                "wifi_strength": 4,
            },
            "last_measurement_timestamp": 1665072044,
        },
    }
