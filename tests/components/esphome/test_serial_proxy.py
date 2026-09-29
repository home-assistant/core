"""Tests for the ESPHome serial proxy helper."""

from collections.abc import Callable
from unittest.mock import AsyncMock, Mock, call, patch

from aioesphomeapi import APIClient
from aioesphomeapi.model import (
    SerialProxyIdentity,
    SerialProxyIdentityFlag,
    SerialProxyIdentitySource,
    SerialProxyInfo,
    SerialProxyPortType,
    UsbDeviceDescriptor,
)
import pytest
from serialx.platforms.serial_esphome import InvalidSettingsError
from yarl import URL

from homeassistant.components.esphome import _async_scan_serial_ports, serial_proxy
from homeassistant.components.esphome.const import DOMAIN
from homeassistant.components.usb import SerialDevice, USBDevice
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


ZBT2 = SerialProxyIdentity(
    instance=0,
    source=SerialProxyIdentitySource.USB,
    flags=SerialProxyIdentityFlag.CONNECTED,
    manufacturer="Nabu Casa",
    product="ZBT-2",
    serial_number="10B41DE58F10",
    usb=UsbDeviceDescriptor(  # type:ignore[call-arg]
        vendor_id=0x303A, product_id=0x4001, bcd_device=0x0101, interface_number=0
    ),
)
ZBT2_REMOVED = SerialProxyIdentity(instance=0, source=SerialProxyIdentitySource.USB)
EMPTY_SOCKET = SerialProxyIdentity(instance=1, source=SerialProxyIdentitySource.USB)
USB_PROXIES = [
    SerialProxyInfo(name="USB (Zigbee)", port_type=SerialProxyPortType.USB_SERIAL),
    SerialProxyInfo(name="USB (Z-Wave)", port_type=SerialProxyPortType.USB_SERIAL),
]


def _mock_identities(
    mock_client: APIClient, identities: list[SerialProxyIdentity]
) -> list[Callable[[SerialProxyIdentity], None]]:
    """Answer the identity subscription the way the device does: one message per port.

    Returns the subscribed callbacks, so a test can deliver a hotplug message.
    """
    callbacks: list[Callable[[SerialProxyIdentity], None]] = []

    def _subscribe(
        on_identity: Callable[[SerialProxyIdentity], None],
    ) -> Callable[[], None]:
        callbacks.append(on_identity)
        for identity in identities:
            on_identity(identity)
        return Mock()

    mock_client.subscribe_serial_proxy_identity = _subscribe
    return callbacks


def _zbt2_port(entry_id: str) -> USBDevice:
    url = str(
        serial_proxy.build_url(entry_id, None, "usb-Nabu_Casa_ZBT-2_10B41DE58F10-if00")
    )
    assert url.endswith("?port_udev_id=usb-Nabu_Casa_ZBT-2_10B41DE58F10-if00")
    return USBDevice(
        device=url,
        resolved_device=url,
        vid="303A",
        pid="4001",
        serial_number="10B41DE58F10",
        manufacturer="Nabu Casa",
        description="ZBT-2",
        bcd_device=0x0101,
        interface_description=None,
        interface_num=0,
    )


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
async def test_scan_serial_ports_uses_project_info(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Project information takes precedence over manufacturer and model."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "manufacturer": "Espressif",
            "model": "ESP32",
            "project_name": "vendor.gadget",
            "serial_proxies": [
                SerialProxyInfo(name="uart0", port_type=SerialProxyPortType.TTL)
            ],
        },
    )

    assert _async_scan_serial_ports(hass) == [
        SerialDevice(
            device=str(serial_proxy.build_url(device.entry.entry_id, "uart0")),
            serial_number="AABBCCDDEEFF-uart0",
            manufacturer="vendor",
            description="gadget (uart0)",
        )
    ]


@pytest.mark.usefixtures("mock_zeroconf")
async def test_scan_serial_ports_defaults_manufacturer(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """A device without a manufacturer falls back to espressif."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "manufacturer": "",
            "model": "ESP32",
            "serial_proxies": [
                SerialProxyInfo(name="uart0", port_type=SerialProxyPortType.TTL)
            ],
        },
    )

    assert _async_scan_serial_ports(hass) == [
        SerialDevice(
            device=str(serial_proxy.build_url(device.entry.entry_id, "uart0")),
            serial_number="AABBCCDDEEFF-uart0",
            manufacturer="espressif",
            description="ESP32 (uart0)",
        )
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
async def test_scan_serial_ports_usb(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """A USB port lists the adapter in it, and an empty socket is not listed."""
    _mock_identities(mock_client, [ZBT2, EMPTY_SOCKET])
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"serial_proxies": USB_PROXIES},
    )

    assert device.entry.runtime_data.serial_proxy_identities == {
        0: ZBT2,
        1: EMPTY_SOCKET,
    }
    assert _async_scan_serial_ports(hass) == [_zbt2_port(device.entry.entry_id)]


@pytest.mark.usefixtures("mock_zeroconf")
async def test_serial_proxy_identity_hotplug(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """An identity change updates the ports and has the usb integration rescan."""
    hass.config.components.add("usb")
    callbacks = _mock_identities(mock_client, [ZBT2, EMPTY_SOCKET])
    with patch(
        "homeassistant.components.usb.async_notify_serial_ports_changed"
    ) as mock_notify:
        device = await mock_esphome_device(
            mock_client=mock_client,
            device_info={"serial_proxies": USB_PROXIES},
        )
        assert mock_notify.mock_calls == [call(hass)] * 2

        callbacks[0](ZBT2_REMOVED)
        assert _async_scan_serial_ports(hass) == []
        assert mock_notify.mock_calls == [call(hass)] * 3

        # The same state again is not a change
        callbacks[0](ZBT2_REMOVED)
        assert mock_notify.mock_calls == [call(hass)] * 3

        # Unreadable descriptors say nothing about what is attached
        callbacks[0](
            SerialProxyIdentity(
                instance=0,
                source=SerialProxyIdentitySource.USB,
                flags=SerialProxyIdentityFlag.CONNECTED | SerialProxyIdentityFlag.ERROR,
            )
        )
        assert _async_scan_serial_ports(hass) == []

        callbacks[0](ZBT2)
        assert _async_scan_serial_ports(hass) == [_zbt2_port(device.entry.entry_id)]
        assert mock_notify.mock_calls == [call(hass)] * 5


@pytest.mark.usefixtures("mock_zeroconf")
async def test_serial_proxy_device_offline(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Losing the ESPHome device takes its USB ports with it until it is back."""
    hass.config.components.add("usb")
    _mock_identities(mock_client, [ZBT2, EMPTY_SOCKET])
    with patch(
        "homeassistant.components.usb.async_notify_serial_ports_changed"
    ) as mock_notify:
        device = await mock_esphome_device(
            mock_client=mock_client,
            device_info={"serial_proxies": USB_PROXIES},
        )
        assert mock_notify.mock_calls == [call(hass)] * 2

        await device.mock_disconnect(expected_disconnect=False)
        assert device.entry.runtime_data.serial_proxy_identities == {}
        assert _async_scan_serial_ports(hass) == []
        assert mock_notify.mock_calls == [call(hass)] * 3

        await device.mock_connect()
        await hass.async_block_till_done()
        assert _async_scan_serial_ports(hass) == [_zbt2_port(device.entry.entry_id)]
        assert mock_notify.mock_calls == [call(hass)] * 5


@pytest.mark.usefixtures("mock_zeroconf")
async def test_async_open_missing_host(hass: HomeAssistant) -> None:
    """A URL with an invalid entry_id raises InvalidSettingsError."""
    assert await async_setup_component(hass, DOMAIN, {})
    proxy = serial_proxy.HassESPHomeSerial("esphome-hass://unknown/?port_name=uart0")

    with pytest.raises(InvalidSettingsError):
        await proxy._async_open()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_async_open_without_port_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Without a port name, finding the port is left to serialx."""
    device = await mock_esphome_device(mock_client=mock_client)
    mock_client._loop = hass.loop

    url = str(
        serial_proxy.build_url(
            device.entry.entry_id, None, "usb-Nabu_Casa_ZBT-2_10B41DE58F10-if00"
        )
    )
    proxy = serial_proxy.HassESPHomeSerial(url)

    with patch(
        "homeassistant.components.esphome.serial_proxy.ESPHomeSerial._async_open",
        AsyncMock(),
    ) as mock_super_open:
        await proxy._async_open()

    assert proxy._api is mock_client
    assert proxy._port_name is None
    assert mock_super_open.mock_calls == [call()]


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
