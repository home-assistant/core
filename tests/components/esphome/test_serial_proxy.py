"""Tests for the ESPHome serial proxy helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, call, patch

from aioesphomeapi import APIClient
from aioesphomeapi.model import SerialProxyInfo, SerialProxyPortType
import pytest
from serialx.platforms.serial_esphome import InvalidSettingsError
from yarl import URL

from homeassistant.components.esphome import _async_scan_serial_ports, serial_proxy
from homeassistant.components.esphome.const import DOMAIN
from homeassistant.components.usb import SerialDevice
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MockESPHomeDeviceType

from tests.common import MockConfigEntry


def test_build_url_basic() -> None:
    """Build a URL with a simple port name."""
    url = serial_proxy.build_url("abc123DEF456", "uart0")
    assert url == URL("esphome-hass://esphome/abc123DEF456?port_name=uart0")


def test_build_url_escapes_port_name() -> None:
    """Port names with special characters are URL-encoded."""
    url = serial_proxy.build_url("abc123", "uart 0/main")
    # Round-trip via yarl recovers the original port name
    assert URL(str(url)).query["port_name"] == "uart 0/main"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_async_setup_stores_event_loop(
    hass: HomeAssistant,
) -> None:
    """async_setup registers hass.loop on the serial_proxy module."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert serial_proxy._HASS_LOOP is hass.loop


async def test_resolve_client_unknown_entry(hass: HomeAssistant) -> None:
    """An unknown entry_id raises InvalidSettingsError."""
    with (
        patch.object(serial_proxy, "async_get_hass", return_value=hass),
        pytest.raises(InvalidSettingsError),
    ):
        await serial_proxy._resolve_client("does-not-exist")


async def test_resolve_client_wrong_domain(hass: HomeAssistant) -> None:
    """A config entry from a different domain raises InvalidSettingsError."""
    entry = MockConfigEntry(domain="other", data={})
    entry.add_to_hass(hass)

    with (
        patch.object(serial_proxy, "async_get_hass", return_value=hass),
        pytest.raises(InvalidSettingsError),
    ):
        await serial_proxy._resolve_client(entry.entry_id)


async def test_resolve_client_unloaded_entry(hass: HomeAssistant) -> None:
    """An ESPHome entry that isn't loaded raises InvalidSettingsError."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    with (
        patch.object(serial_proxy, "async_get_hass", return_value=hass),
        pytest.raises(InvalidSettingsError),
    ):
        await serial_proxy._resolve_client(entry.entry_id)


@pytest.mark.usefixtures("mock_zeroconf")
async def test_resolve_client_loaded_entry(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """A loaded ESPHome entry returns its APIClient."""
    device = await mock_esphome_device(mock_client=mock_client)

    with patch.object(serial_proxy, "async_get_hass", return_value=hass):
        client = await serial_proxy._resolve_client(device.entry.entry_id)

    assert client is mock_client


@pytest.mark.usefixtures("mock_zeroconf")
async def test_scan_serial_ports_no_entries(hass: HomeAssistant) -> None:
    """No loaded ESPHome entries yields no ports."""
    assert _async_scan_serial_ports(hass) == []


@pytest.mark.usefixtures("mock_zeroconf")
async def test_scan_serial_ports_happy_path(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """A loaded entry with serial proxies emits a SerialDevice per proxy."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "manufacturer": "Espressif",
            "model": "ESP32",
            "serial_proxies": [
                SerialProxyInfo(name="Left Port", port_type=SerialProxyPortType.TTL),
                SerialProxyInfo(name="Right Port", port_type=SerialProxyPortType.TTL),
            ],
        },
    )

    ports = _async_scan_serial_ports(hass)

    entry_id = device.entry.entry_id
    assert ports == [
        SerialDevice(
            device=str(serial_proxy.build_url(entry_id, "Left Port")),
            serial_number="AABBCCDDEEFF-left_port",
            manufacturer="Espressif",
            description="ESP32 (Left Port)",
        ),
        SerialDevice(
            device=str(serial_proxy.build_url(entry_id, "Right Port")),
            serial_number="AABBCCDDEEFF-right_port",
            manufacturer="Espressif",
            description="ESP32 (Right Port)",
        ),
    ]


@pytest.mark.usefixtures("mock_zeroconf")
async def test_scan_serial_ports_skips_unavailable(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Unavailable entries are skipped by the scanner."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "serial_proxies": [
                SerialProxyInfo(name="uart0", port_type=SerialProxyPortType.TTL)
            ],
        },
    )
    # Mark the entry as unavailable
    device.entry.runtime_data.available = False

    assert _async_scan_serial_ports(hass) == []


@pytest.mark.usefixtures("mock_zeroconf")
async def test_async_open_missing_host(hass: HomeAssistant) -> None:
    """A URL with an invalid entry_id raises InvalidSettingsError."""
    assert await async_setup_component(hass, DOMAIN, {})
    proxy = serial_proxy.HassESPHomeSerial("esphome-hass://unknown/?port_name=uart0")

    with pytest.raises(InvalidSettingsError):
        await proxy._async_open()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_async_open_missing_port_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """A URL with a missing port name raises InvalidSettingsError."""
    assert await async_setup_component(hass, DOMAIN, {})

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "manufacturer": "Espressif",
            "model": "ESP32",
            "serial_proxies": [
                SerialProxyInfo(name="uart0", port_type=SerialProxyPortType.TTL),
            ],
        },
    )

    entry_id = device.entry.entry_id
    proxy = serial_proxy.HassESPHomeSerial(f"esphome-hass://{entry_id}")

    with pytest.raises(InvalidSettingsError):
        await proxy._async_open()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_async_open_happy_path(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Happy path sets _api from the loaded entry and applies port_name from query."""
    device = await mock_esphome_device(mock_client=mock_client)
    mock_client._loop = hass.loop

    url = str(serial_proxy.build_url(device.entry.entry_id, "uart0"))
    proxy = serial_proxy.HassESPHomeSerial(url)

    with patch(
        "homeassistant.components.esphome.serial_proxy.ESPHomeSerial._async_open",
        AsyncMock(),
    ) as mock_super_open:
        await proxy._async_open()

    assert proxy._api is mock_client
    assert proxy._port_name == "uart0"
    assert proxy._client_loop is hass.loop
    assert mock_super_open.mock_calls == [call()]
