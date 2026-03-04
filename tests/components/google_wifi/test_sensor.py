"""The tests for the Google Wifi platform."""

from unittest.mock import patch

import requests

from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_WIFI_DATA = {
    "system": {
        "uptime": 86400,  # Exactly 1 day
        "version": "14150.376.32",
    },
    "wan": {"online": True, "localIpAddress": "192.168.86.1"},
    "software": {"updateNewVersion": "0.0.0.0"},
}


async def test_sensor_values(hass: HomeAssistant) -> None:
    """Test sensor states match mocked data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "192.168.86.1", "name": "Google Wifi"},
        entry_id="test_entry_id"
    )
    entry.add_to_hass(hass)

    # Patch the requests call inside sensor.py
    with patch("homeassistant.components.google_wifi.sensor.requests.get") as mock_get:
        mock_get.return_value.json.return_value = MOCK_WIFI_DATA
        mock_get.return_value.status_code = 200

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # The entity_id in HA is generated from the name: "Google Wifi Uptime" -> "sensor.google_wifi_uptime"
        # because _attr_has_entity_name = True and the entry title is "Google Wifi"

        # Check Uptime Sensor
        state = hass.states.get("sensor.google_wifi_uptime")
        assert state is not None
        assert state.state == "1.0"

        # Check Status Sensor
        state = hass.states.get("sensor.google_wifi_status")
        assert state.state == "Online"

        # Check New Version Sensor
        state = hass.states.get("sensor.google_wifi_new_version")
        assert state.state == "Latest"

async def test_sensor_update_failed(hass: HomeAssistant) -> None:
    """Test sensor handles API errors gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1", CONF_NAME: "Google Wifi"},
        entry_id="test_fail"
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google_wifi.sensor.requests.get",
        side_effect=requests.exceptions.RequestException,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.google_wifi_uptime")
    # In your code, if fetch fails, _attr_data becomes {} and native_value returns None
    assert state.state == "unknown"
