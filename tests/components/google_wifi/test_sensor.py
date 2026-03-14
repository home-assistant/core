"""The tests for the Google Wifi platform."""

from unittest.mock import patch

import requests

from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.components.google_wifi.sensor import async_setup_platform
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry

MOCK_WIFI_DATA = {
    "system": {
        "uptime": 86400,
        "modelId": "test_model_123",  # Required for DeviceInfo
    },
    "wan": {
        "online": True,
        "localIpAddress": "192.168.86.1",
    },
    "software": {
        "softwareVersion": "14150.376.32",  # Required for DeviceInfo
        "updateNewVersion": "0.0.0.0",
    },
}


async def test_sensor_values(hass: HomeAssistant) -> None:
    """Test sensor states match mocked API data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.86.1", CONF_NAME: "Google Wifi"},
        title="Google Wifi",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.google_wifi.sensor.requests.get") as mock_get:
        # Properly configure the mock response
        mock_response = mock_get.return_value
        mock_response.json.return_value = MOCK_WIFI_DATA
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Force an update to ensure the mock data is processed
        await async_update_entity(hass, "sensor.google_wifi_uptime")
        await async_update_entity(hass, "sensor.google_wifi_status")
        await async_update_entity(hass, "sensor.google_wifi_new_version")
        await hass.async_block_till_done()

        # Check Uptime Sensor
        state = hass.states.get("sensor.google_wifi_uptime")
        assert state is not None
        assert state.state == "1.0"

        # Check Status Sensor (True -> Online)
        state = hass.states.get("sensor.google_wifi_status")
        assert state.state == "Online"

        # Check Version Sensor (0.0.0.0 -> Latest)
        state = hass.states.get("sensor.google_wifi_new_version")
        assert state.state == "Latest"


async def test_sensor_update_failed(hass: HomeAssistant) -> None:
    """Test sensor handles API errors gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1", CONF_NAME: "Google Wifi"},
        title="Google Wifi",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google_wifi.sensor.requests.get",
        side_effect=requests.exceptions.RequestException,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.google_wifi_uptime")
    # If the first update fails, the state will be 'unknown'
    assert state is not None
    assert state.state == "unknown"


async def test_legacy_yaml_import_in_sensor(hass: HomeAssistant) -> None:
    """Test the legacy async_setup_platform in sensor.py."""
    with (
        patch("homeassistant.helpers.issue_registry.async_create_issue") as mock_issue,
        patch(
            "homeassistant.config_entries.ConfigEntriesFlowManager.async_init"
        ) as mock_init,
    ):
        # Pass a dummy lambda for the add_entities callback
        await async_setup_platform(
            hass, {CONF_IP_ADDRESS: "192.168.86.1"}, lambda x, y=None: None
        )
        await hass.async_block_till_done()

        mock_issue.assert_called_once()
        mock_init.assert_called_once()
