"""Test the WatchYourLAN sensor platform."""

from http import HTTPStatus
from unittest.mock import patch

import pytest
import respx

from homeassistant.components.watchyourlan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_sensors(hass: HomeAssistant) -> None:
    """Test setup of the WatchYourLAN sensors with valid API response."""
    # Mock API response
    devices = [
        {
            "ID": 1,
            "Name": "Device 1",
            "DNS": "",
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
            "DNS": "",
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
        # Create a mock config entry, now including the 'url' key
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

        # Ensure the sensors were created with correct entity IDs
        state_1 = hass.states.get("sensor.watchyourlan_1_device_1")
        state_2 = hass.states.get("sensor.watchyourlan_2_device_2")

        assert state_1 is not None
        assert state_1.state == "Online"
        assert state_1.attributes["IP"] == "192.168.1.100"

        assert state_2 is not None
        assert state_2.state == "Offline"
        assert state_2.attributes["IP"] == "192.168.1.101"


@respx.mock
async def test_api_timeout(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the sensor when there is an API timeout."""
    # Simulate a timeout error on the API request
    respx.get("http://127.0.0.1:8840/api/all").mock(side_effect=TimeoutError)

    # Mock the WatchYourLANUpdateCoordinator to avoid network access
    with (
        patch(
            "homeassistant.components.watchyourlan.sensor.WatchYourLANUpdateCoordinator._async_update_data",
            side_effect=TimeoutError,
        ),
        patch(
            "homeassistant.components.watchyourlan.sensor.WatchYourLANUpdateCoordinator._schedule_refresh",
            return_value=None,
        ),
    ):
        # Create a mock config entry
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

        # Ensure no entities were created due to the timeout
        state = hass.states.get("sensor.watchyourlan_1_device_1")
        assert state is None

        # Verify the logs contain ConfigEntryNotReady error
        assert "ConfigEntryNotReady" in caplog.text


@respx.mock
async def test_sensor_state_after_update(hass: HomeAssistant) -> None:
    """Test the sensor state after a manual update."""
    # Mock initial response
    devices = [
        {
            "ID": 1,
            "Name": "Device 1",
            "DNS": "",
            "Iface": "eth0",
            "Mac": "11:22:33:44:55:66",
            "Hw": "Acme, Inc.",
            "Date": "2024-09-01 00:00:00",
            "Known": 1,
            "Now": 1,
            "IP": "192.168.1.100",
        },
    ]

    # Mock the API response for the WatchYourLAN devices
    respx.get("http://127.0.0.1:8840/api/all").respond(
        status_code=HTTPStatus.OK, json=devices
    )

    # Mock the WatchYourLANUpdateCoordinator to avoid network access
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
        # Create a mock config entry
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

        # Set up the Home Assistant Core component so the update_entity service is available
        await async_setup_component(hass, "homeassistant", {})

        # Set up the sensor platform
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Ensure the sensor is created with the correct state
        state = hass.states.get("sensor.watchyourlan_1_device_1")
        assert state is not None
        assert state.state == "Online"
        assert state.attributes["IP"] == "192.168.1.100"

        # Simulate an updated API response (device goes offline)
        devices[0]["Now"] = 0
        respx.get("http://127.0.0.1:8840/api/all").respond(
            status_code=HTTPStatus.OK, json=devices
        )

        # Trigger a manual update
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": "sensor.watchyourlan_1_device_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Check if the state was updated
        state = hass.states.get("sensor.watchyourlan_1_device_1")
        assert state.state == "Offline"
