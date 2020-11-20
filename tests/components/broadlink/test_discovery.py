"""Tests for device discovery."""
import socket

import pytest

from homeassistant.components.broadlink.const import DOMAIN

from . import get_device

from tests.async_mock import patch


async def test_discovery_new_devices_single_netif(hass):
    """Test we create flows for new devices discovered (single network)."""
    devices = ["Entrance", "Bedroom", "Living Room", "Office"]
    mock_apis = [get_device(device).get_mock_api() for device in devices]
    results = [("192.168.0.255", mock_apis)]

    device = get_device("Office")
    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        *_, mock_discovery = await device.setup_entry(hass, mock_discovery=results)

    assert mock_discovery.call_count == 1
    assert mock_init.call_count == len(devices) - 1


async def test_discovery_new_devices_mult_netifs(hass):
    """Test we create config flows for new devices discovered (multiple networks)."""
    devices_a = ["Entrance", "Bedroom", "Living Room", "Office"]
    devices_b = ["Garden", "Rooftop"]
    mock_apis_a = [get_device(device).get_mock_api() for device in devices_a]
    mock_apis_b = [get_device(device).get_mock_api() for device in devices_b]
    results = [("192.168.0.255", mock_apis_a), ("192.168.1.255", mock_apis_b)]

    device = get_device("Office")
    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        *_, mock_discovery = await device.setup_entry(hass, mock_discovery=results)

    assert mock_discovery.call_count == 2
    assert mock_init.call_count == len(devices_a) + len(devices_b) - 1


async def test_discovery_no_devices(hass):
    """Test we do not create flows if no devices are discovered."""
    results = [("192.168.0.255", [])]

    device = get_device("Office")
    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        *_, mock_discovery = await device.setup_entry(hass, mock_discovery=results)

    assert mock_discovery.call_count == 1
    assert mock_init.call_count == 0


async def test_discovery_already_known_device(hass):
    """Test we do not create a flow when a known device is discovered."""
    device_a = get_device("Living Room")
    mock_entry = device_a.get_mock_entry()
    mock_entry.add_to_hass(hass)
    results = device_a.get_mock_discovery()

    device_b = get_device("Bedroom")
    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        *_, mock_discovery = await device_b.setup_entry(hass, mock_discovery=results)

    assert mock_discovery.call_count == 1
    assert mock_init.call_count == 0


async def test_discovery_unsupported_device(hass):
    """Test we do not create a flow when an unsupported device is discovered."""
    unsupported_device = get_device("Kitchen")
    results = unsupported_device.get_mock_discovery()

    device = get_device("Entrance")
    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        *_, mock_discovery = await device.setup_entry(hass, mock_discovery=results)

    assert mock_discovery.call_count == 1
    assert mock_init.call_count == 0


async def test_discovery_update_ip_address(hass):
    """Test we update the entry when a known device is discovered with a different IP address."""
    device = get_device("Living Room")
    _, mock_entry, _ = await device.setup_entry(hass)

    previous_host = device.host
    device.host = "192.168.1.128"
    results = device.get_mock_discovery() * 2

    with device.patch_setup(mock_discovery=results), patch(
        "homeassistant.components.broadlink.helpers.socket.gethostbyname",
        return_value=previous_host,
    ) as mock_host:
        await hass.data[DOMAIN].discovery.coordinator.async_refresh()
        await hass.async_block_till_done()

    assert mock_host.call_count == 2
    assert mock_entry.data["host"] == device.host


async def test_discovery_update_hostname(hass):
    """Test we update the entry when the hostname is no longer valid."""
    device = get_device("Living Room")
    results = device.get_mock_discovery()
    device.host = "invalidhostname"

    _, mock_entry, _ = await device.setup_entry(hass, mock_discovery=results)

    device.host = "192.168.1.128"
    results = device.get_mock_discovery() * 2

    with device.patch_setup(mock_discovery=results), patch(
        "homeassistant.components.broadlink.helpers.socket.gethostbyname",
        side_effect=OSError(socket.EAI_NONAME, None),
    ) as mock_host:
        await hass.data[DOMAIN].discovery.coordinator.async_refresh()
        await hass.async_block_till_done()

    assert mock_host.call_count == 2
    assert mock_entry.data["host"] == device.host


async def test_discovery_do_not_change_hostname(hass):
    """Test we do not update the entry if the hostname routes to the device."""
    device = get_device("Living Room")
    results = device.get_mock_discovery()
    device.host = "somethingthatworks"

    _, mock_entry, _ = await device.setup_entry(hass, mock_discovery=results)

    with device.patch_setup(mock_discovery=results), patch(
        "homeassistant.components.broadlink.helpers.socket.gethostbyname",
        return_value=device.host,
    ) as mock_host:
        await hass.data[DOMAIN].discovery.coordinator.async_refresh()
        await hass.async_block_till_done()

    assert mock_host.call_count == 1
    assert mock_entry.data["host"] == "somethingthatworks"


async def test_discovery_ignore_os_error(hass):
    """Test we do not propagate an OS error during a discovery."""
    device = get_device("Living Room")
    _, mock_entry, _ = await device.setup_entry(hass)

    with patch.object(hass.config_entries.flow, "async_init") as mock_init, patch(
        "homeassistant.components.broadlink.get_broadcast_addrs",
        return_value=["192.168.31.0"],
    ), patch(
        "homeassistant.components.broadlink.discovery.blk.xdiscover",
        side_effect=OSError(),
    ) as mock_discovery:
        try:
            await hass.data[DOMAIN].discovery.coordinator.async_refresh()
            await hass.async_block_till_done()
        except OSError:
            pytest.fail("Device discovery propagated an OSError")

    assert mock_discovery.call_count == 1
    assert mock_init.call_count == 0


async def test_discovery_run_once(hass):
    """Test we only run discovery once at startup."""
    devices = ["Entrance", "Bedroom", "Living Room", "Office"]
    num_calls = 0

    for device in map(get_device, devices):
        *_, mock_discovery = await device.setup_entry(hass)
        num_calls += mock_discovery.call_count

    assert num_calls == 1
