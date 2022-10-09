"""Test Enphase Envoy diagnostics."""
from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_enphase_envoy):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "title": "Envoy 1234",
            "data": {
                "host": "1.1.1.1",
                "name": "Envoy 1234",
                "username": REDACTED,
                "password": REDACTED,
            },
        },
        "data": {
            "production": 1840,
            "daily_production": 28223,
            "seven_days_production": 174482,
            "lifetime_production": 5924391,
            "consumption": 1840,
            "daily_consumption": 5923857,
            "seven_days_consumption": 5923857,
            "lifetime_consumption": 5923857,
            "inverters_production": {
                "202140024014": [136, "2022-10-08 16:43:36"],
                "202140023294": [163, "2022-10-08 16:43:41"],
                "202140013819": [130, "2022-10-08 16:43:31"],
                "202140023794": [139, "2022-10-08 16:43:38"],
                "202140023381": [130, "2022-10-08 16:43:47"],
                "202140024176": [54, "2022-10-08 16:43:59"],
                "202140003284": [132, "2022-10-08 16:43:55"],
                "202140019854": [129, "2022-10-08 16:43:58"],
                "202140020743": [131, "2022-10-08 16:43:49"],
                "202140023531": [28, "2022-10-08 16:43:53"],
                "202140024241": [164, "2022-10-08 16:43:33"],
                "202140022963": [164, "2022-10-08 16:43:41"],
                "202140023149": [118, "2022-10-08 16:43:47"],
                "202140024828": [129, "2022-10-08 16:43:36"],
                "202140023269": [133, "2022-10-08 16:43:43"],
                "202140024157": [112, "2022-10-08 16:43:52"],
            },
        },
    }
