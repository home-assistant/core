"""The tests for the Google Wifi platform."""

from unittest.mock import patch

from custom_components.google_wifi.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

MOCK_WIFI_DATA = {
    "system": {
        "uptime": 86400,  # Exactly 1 day
        "version": "14150.376.32",
        "newVersion": "0.0.0.0",
    },
    "wan": {"online": True, "localIpAddress": "192.168.86.1"},
}


async def test_sensor_values(hass: HomeAssistant) -> None:
    """Test sensor states match mocked coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "192.168.86.1", "name": "Google Wifi"},
    )
    entry.add_to_hass(hass)

    with patch("custom_components.google_wifi.coordinator.requests.get") as mock_get:
        # Mock the API response
        mock_get.return_value.json.return_value = MOCK_WIFI_DATA
        mock_get.return_value.status_code = 200

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check Uptime Sensor (should be rounded to 1.0 days)
        state = hass.states.get("sensor.google_wifi_uptime")
        assert state is not None
        assert state.state == "1.0"

        # Check Status Sensor (should be "Online")
        state = hass.states.get("sensor.google_wifi_status")
        assert state.state == "Online"

        # Check Version Sensor (should be "Latest" if 0.0.0.0)
        state = hass.states.get("sensor.google_wifi_new_version")
        assert state.state == "Latest"
