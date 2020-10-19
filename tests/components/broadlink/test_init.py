"""Tests for the initialization of the Broadlink integration."""
import socket

import pytest

from homeassistant.components import broadlink
from homeassistant.setup import async_setup_component

from . import get_device

from tests.async_mock import patch

DISCOVERY = "homeassistant.components.broadlink.discovery.blk.discover"


@pytest.fixture(autouse=True)
def broadlink_setup_fixture():
    """Mock broadlink entry setup."""
    with patch(
        "homeassistant.components.broadlink.async_setup_entry", return_value=True
    ):
        yield


async def test_setup_new_devices_discovered(hass):
    """Test we create config flows for new devices discovered at startup."""
    devices = ["Entrance", "Bedroom", "Living Room", "Office"]
    mock_apis = [get_device(device).get_mock_api() for device in devices]

    with patch(DISCOVERY, return_value=mock_apis) as mock_discover, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        assert await async_setup_component(hass, broadlink.DOMAIN, {}) is True

    assert mock_discover.call_count == 1
    assert mock_init.call_count == len(devices)


async def test_setup_no_devices_discovered(hass):
    """Test we do not create flows if no devices are discovered at startup."""
    with patch(DISCOVERY, return_value=[]) as mock_discover, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        assert await async_setup_component(hass, broadlink.DOMAIN, {}) is True

    assert mock_discover.call_count == 1
    assert mock_init.call_count == 0


async def test_setup_discover_already_known_host(hass):
    """Test we do not create flows for known devices discovered at startup."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()

    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch(DISCOVERY, return_value=[mock_api]) as mock_discover, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        assert await async_setup_component(hass, broadlink.DOMAIN, {}) is True

    assert mock_discover.call_count == 1
    assert mock_init.call_count == 0


async def test_setup_discover_update_ip_address(hass):
    """Test we update the entry if a known device is discovered with a different IP address."""
    device = get_device("Living Room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    previous_host = device.host
    device.host = "192.168.1.128"
    mock_api = device.get_mock_api()

    with patch(DISCOVERY, return_value=[mock_api]) as mock_discover, patch(
        "homeassistant.components.broadlink.helpers.socket.gethostbyname",
        return_value=previous_host,
    ):
        assert await async_setup_component(hass, broadlink.DOMAIN, {}) is True

    assert mock_discover.call_count == 1
    assert mock_entry.data["host"] == device.host


async def test_setup_discover_update_hostname(hass):
    """Test we update the entry if the hostname is no longer valid."""
    device = get_device("Living Room")
    device.host = "invalidhostname.local"
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device.host = "192.168.1.128"
    mock_api = device.get_mock_api()

    with patch(DISCOVERY, return_value=[mock_api]) as mock_discover, patch(
        "homeassistant.components.broadlink.helpers.socket.gethostbyname",
        side_effect=OSError(socket.EAI_NONAME, None),
    ):
        assert await async_setup_component(hass, broadlink.DOMAIN, {}) is True

    assert mock_discover.call_count == 1
    assert mock_entry.data["host"] == device.host


async def test_setup_discover_do_not_change_hostname(hass):
    """Test we do not update the entry if the hostname routes to the device."""
    device = get_device("Living Room")
    device.host = "somethingthatworks.local"
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device.host = "192.168.1.128"
    mock_api = device.get_mock_api()

    with patch(DISCOVERY, return_value=[mock_api]) as mock_discover, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init, patch(
        "homeassistant.components.broadlink.helpers.socket.gethostbyname",
        return_value=device.host,
    ):
        assert await async_setup_component(hass, broadlink.DOMAIN, {}) is True

    assert mock_discover.call_count == 1
    assert mock_init.call_count == 0
    assert mock_entry.data["host"] == "somethingthatworks.local"
