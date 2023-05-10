"""Test Ambient PWS diagnostics."""
from homeassistant.components.ambient_station import DOMAIN
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    data_station,
    setup_config_entry,
) -> None:
    """Test config entry diagnostics."""
    ambient = hass.data[DOMAIN][config_entry.entry_id]
    ambient.stations = data_station
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 2,
            "domain": "ambient_station",
            "title": REDACTED,
            "data": {"api_key": REDACTED, "app_key": REDACTED},
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
        },
        "stations": {
            "devices": [
                {
                    "macAddress": REDACTED,
                    "lastData": {
                        "dateutc": 1642631880000,
                        "tempinf": 70.9,
                        "humidityin": 29,
                        "baromrelin": 29.953,
                        "baromabsin": 25.016,
                        "tempf": 21,
                        "humidity": 87,
                        "winddir": 25,
                        "windspeedmph": 0.2,
                        "windgustmph": 1.1,
                        "maxdailygust": 9.2,
                        "hourlyrainin": 0,
                        "eventrainin": 0,
                        "dailyrainin": 0,
                        "weeklyrainin": 0,
                        "monthlyrainin": 0.409,
                        "totalrainin": 35.398,
                        "solarradiation": 11.62,
                        "uv": 0,
                        "batt_co2": 1,
                        "feelsLike": 21,
                        "dewPoint": 17.75,
                        "feelsLikein": 69.1,
                        "dewPointin": 37,
                        "lastRain": "2022-01-07T19:45:00.000Z",
                        "deviceId": REDACTED,
                        "tz": REDACTED,
                        "date": "2022-01-19T22:38:00.000Z",
                    },
                    "info": {"name": "Side Yard", "location": REDACTED},
                    "apiKey": REDACTED,
                }
            ],
            "method": "subscribe",
        },
    }
