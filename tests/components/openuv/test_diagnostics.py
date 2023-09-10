"""Test OpenUV diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_config_entry,
) -> None:
    """Test config entry diagnostics."""
    await async_setup_component(hass, "homeassistant", {})
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 2,
            "domain": "openuv",
            "title": REDACTED,
            "data": {
                "api_key": REDACTED,
                "elevation": 0,
                "latitude": REDACTED,
                "longitude": REDACTED,
            },
            "options": {"from_window": 3.5, "to_window": 3.5},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
        },
        "data": {
            "protection_window": {
                "from_time": "2018-07-30T15:17:49.750Z",
                "from_uv": 3.2509,
                "to_time": "2018-07-30T22:47:49.750Z",
                "to_uv": 3.6483,
            },
            "uv": {
                "uv": 8.2342,
                "uv_time": "2018-07-30T20:53:06.302Z",
                "uv_max": 10.3335,
                "uv_max_time": "2018-07-30T19:07:11.505Z",
                "ozone": 300.7,
                "ozone_time": "2018-07-30T18:07:04.466Z",
                "safe_exposure_time": {
                    "st1": 20,
                    "st2": 24,
                    "st3": 32,
                    "st4": 40,
                    "st5": 65,
                    "st6": 121,
                },
                "sun_info": {
                    "sun_times": {
                        "solarNoon": "2018-07-30T19:07:11.505Z",
                        "nadir": "2018-07-30T07:07:11.505Z",
                        "sunrise": "2018-07-30T11:57:49.750Z",
                        "sunset": "2018-07-31T02:16:33.259Z",
                        "sunriseEnd": "2018-07-30T12:00:53.253Z",
                        "sunsetStart": "2018-07-31T02:13:29.756Z",
                        "dawn": "2018-07-30T11:27:27.911Z",
                        "dusk": "2018-07-31T02:46:55.099Z",
                        "nauticalDawn": "2018-07-30T10:50:01.621Z",
                        "nauticalDusk": "2018-07-31T03:24:21.389Z",
                        "nightEnd": "2018-07-30T10:08:47.846Z",
                        "night": "2018-07-31T04:05:35.163Z",
                        "goldenHourEnd": "2018-07-30T12:36:14.026Z",
                        "goldenHour": "2018-07-31T01:38:08.983Z",
                    },
                    "sun_position": {
                        "azimuth": 0.9567419441563509,
                        "altitude": 1.0235714275875594,
                    },
                },
            },
        },
    }
