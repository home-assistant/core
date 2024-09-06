"""Test the WatchYourLAN sensor platform."""

from unittest.mock import patch

from homeassistant.components.watchyourlan.const import DOMAIN
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

    # Mock the WatchYourLANUpdateCoordinator to return the devices without trying to fetch data
    with (
        patch(
            "homeassistant.components.watchyourlan.sensor.WatchYourLANUpdateCoordinator._async_update_data",
            return_value=devices,
        ),
        patch(
            "homeassistant.components.watchyourlan.sensor.WatchYourLANUpdateCoordinator._schedule_refresh",
            return_value=None,
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "127.0.0.1",
                "port": 8840,
                "ssl": False,
                "url": "http://127.0.0.1:8840",
            },
        )
        entry.add_to_hass(hass)

        # Set up the sensor platform
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check online status sensor
        state_1 = hass.states.get("sensor.online_status")
        assert state_1 is not None
        assert state_1.state == "Online"

        # Check device attributes (IP sensor)
        state_ip_1 = hass.states.get("sensor.ip_address")
        assert state_ip_1 is not None
        assert state_ip_1.state == "192.168.1.100"

        # Check the MAC sensor
        state_mac_1 = hass.states.get("sensor.mac_address")
        assert state_mac_1 is not None
        assert state_mac_1.state == "11:22:33:44:55:66"


async def test_device_count_sensor(hass: HomeAssistant) -> None:
    """Test the WatchYourLAN device count sensor."""
    devices = [
        {"ID": 1, "Now": 1, "Known": 1, "Iface": "eth0"},
        {"ID": 2, "Now": 0, "Known": 1, "Iface": "eth1"},
        {"ID": 3, "Now": 1, "Known": 0, "Iface": "eth0"},
    ]

    # Mock the WatchYourLANUpdateCoordinator to return the devices
    with (
        patch(
            "homeassistant.components.watchyourlan.sensor.WatchYourLANUpdateCoordinator._async_update_data",
            return_value=devices,
        ),
        patch(
            "homeassistant.components.watchyourlan.sensor.WatchYourLANUpdateCoordinator._schedule_refresh",
            return_value=None,
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "127.0.0.1",
                "port": 8840,
                "ssl": False,
                "url": "http://127.0.0.1:8840",
            },
        )
        entry.add_to_hass(hass)

        # Set up the sensor platform
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check the total devices sensor
        state = hass.states.get("sensor.watchyourlan_total_devices")
        assert state is not None
        assert state.state == "3"

        # Check extra attributes for device counts
        assert state.attributes["online"] == 2
        assert state.attributes["offline"] == 1
        assert state.attributes["known"] == 2
        assert state.attributes["unknown"] == 1
        assert state.attributes["devices_per_iface"] == {"eth0": 2, "eth1": 1}


async def test_sensor_state_update(hass: HomeAssistant) -> None:
    """Test that the sensor state is updated properly."""
    devices = [
        {
            "ID": 1,
            "Now": 1,
            "Iface": "eth0",
            "IP": "192.168.1.100",
            "Mac": "11:22:33:44:55:66",
        }
    ]

    # Mock the WatchYourLANUpdateCoordinator
    with patch(
        "homeassistant.components.watchyourlan.sensor.WatchYourLANUpdateCoordinator._async_update_data",
        return_value=devices,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "127.0.0.1",
                "port": 8840,
                "ssl": False,
                "url": "http://127.0.0.1:8840",
            },
        )
        entry.add_to_hass(hass)

        # Set up the sensor platform
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state_1 = hass.states.get("sensor.online_status")
        assert state_1.state == "Online"

        # Simulate device going offline and update sensor
        devices[0]["Now"] = 0
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        state_1 = hass.states.get("sensor.online_status")
        assert state_1.state == "Offline"


async def test_restore_sensor_state(hass: HomeAssistant) -> None:
    """Test restoring sensor state after Home Assistant restart."""
    devices = [
        {
            "ID": 1,
            "Now": 1,
            "Iface": "eth0",
            "IP": "192.168.1.100",
            "Mac": "11:22:33:44:55:66",
        }
    ]

    with patch(
        "homeassistant.components.watchyourlan.sensor.WatchYourLANUpdateCoordinator._async_update_data",
        return_value=devices,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "127.0.0.1",
                "port": 8840,
                "ssl": False,
                "url": "http://127.0.0.1:8840",
            },
        )
        entry.add_to_hass(hass)

        # Set up the sensor platform
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Ensure the sensor is created
        state_1 = hass.states.get("sensor.online_status")
        assert state_1.state == "Online"

        # Simulate a restart and test if the state is restored
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state_1 = hass.states.get("sensor.online_status")
        assert state_1.state == "Online"  # Ensure state is restored
