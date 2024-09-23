"""Test the WatchYourLAN sensor platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.watchyourlan.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_sensors(hass: HomeAssistant) -> None:
    """Test setup of the WatchYourLAN sensors with valid API response."""
    devices = [
        {
            "ID": 1,
            "Name": "Device 1",
            "Iface": "eth0",
            "IP": "192.168.1.100",
            "Mac": "11:22:33:44:55:66",
            "Hw": "Acme, Inc.",
            "Date": "2024-09-01 00:00:00",
            "Known": 1,
            "Now": 1,
        },
        {
            "ID": 2,
            "Name": "Device 2",
            "Iface": "eth1",
            "IP": "192.168.1.101",
            "Mac": "66:55:44:33:22:11",
            "Hw": "Acme, Inc.",
            "Date": "2024-09-01 23:59:59",
            "Known": 1,
            "Now": 0,
        },
    ]

    # Mock the WatchYourLANClient in the coordinator where it's used
    with patch(
        "homeassistant.components.watchyourlan.coordinator.WatchYourLANClient.get_all_hosts",
        AsyncMock(return_value=devices),  # Ensure it returns a coroutine
    ):
        mock_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_URL: "http://127.0.0.1:8840"},
        )
        mock_entry.add_to_hass(hass)

        # Set up the sensor platform
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        # Check device attributes (IP sensor)
        state_ip_1 = hass.states.get("sensor.watchyourlan_1_ip")
        assert state_ip_1 is not None
        assert state_ip_1.state == "192.168.1.100"

        # Check the MAC sensor
        state_mac_1 = hass.states.get("sensor.watchyourlan_1_iface")
        assert state_mac_1 is not None
        assert state_mac_1.state == "eth0"
