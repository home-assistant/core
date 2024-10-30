"""Test the WatchYourLAN sensor platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant


async def test_setup_sensors(hass: HomeAssistant, mock_config_entry) -> None:
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
        # mock_config_entry fixture is now used, no need to manually create the config entry
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check device attributes (IP sensor)
        state_ip_1 = hass.states.get("sensor.watchyourlan_11_22_33_44_55_66_ip")
        assert state_ip_1 is not None
        assert state_ip_1.state == "192.168.1.100"

        # Check the Interface sensor for Device 1
        state_iface_1 = hass.states.get("sensor.watchyourlan_11_22_33_44_55_66_iface")
        assert state_iface_1 is not None
        assert state_iface_1.state == "eth0"

        # Check device attributes (IP sensor) for Device 2
        state_ip_2 = hass.states.get("sensor.watchyourlan_66_55_44_33_22_11_ip")
        assert state_ip_2 is not None
        assert state_ip_2.state == "192.168.1.101"

        # Check the Interface sensor for Device 2
        state_iface_2 = hass.states.get("sensor.watchyourlan_66_55_44_33_22_11_iface")
        assert state_iface_2 is not None
        assert state_iface_2.state == "eth1"
