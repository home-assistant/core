"""ESPHome set up tests."""

from unittest.mock import AsyncMock, Mock
from urllib.parse import quote

from aioesphomeapi import APIConnectionError, SerialProxyInfo
import pytest

from homeassistant.components.esphome import DOMAIN
from homeassistant.components.esphome.const import CONF_NOISE_PSK
from homeassistant.components.esphome.encryption_key_storage import (
    async_get_encryption_key_storage,
)
from homeassistant.components.usb import SerialDevice, async_scan_serial_ports
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDeviceType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_client", "mock_zeroconf")
async def test_remove_entry(hass: HomeAssistant) -> None:
    """Test we can remove an entry without error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="mock-config-name",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_clears_dynamic_encryption_key(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that removing an entry clears the dynamic encryption key from device and storage."""
    # Store the encryption key to simulate it was dynamically generated
    storage = await async_get_encryption_key_storage(hass)
    await storage.async_store_key(
        mock_config_entry.unique_id, mock_config_entry.data[CONF_NOISE_PSK]
    )
    assert (
        await storage.async_get_key(mock_config_entry.unique_id)
        == mock_config_entry.data[CONF_NOISE_PSK]
    )

    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.connect.assert_called_once()
    mock_client.noise_encryption_set_key.assert_called_once_with(b"")
    mock_client.disconnect.assert_called_once()

    assert await storage.async_get_key(mock_config_entry.unique_id) is None


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_no_noise_psk(hass: HomeAssistant, mock_client) -> None:
    """Test that removing an entry without noise_psk does not attempt to clear encryption key."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            # No CONF_NOISE_PSK
        },
        unique_id="11:22:33:44:55:aa",
    )
    mock_config_entry.add_to_hass(hass)

    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.noise_encryption_set_key.assert_not_called()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_user_provided_key(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that removing an entry with user-provided key does not clear it."""
    # Do not store the key in storage - simulates user-provided key
    storage = await async_get_encryption_key_storage(hass)
    assert await storage.async_get_key(mock_config_entry.unique_id) is None

    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.noise_encryption_set_key.assert_not_called()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_device_rejects_key_removal(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that when device rejects key removal, key remains in storage."""
    # Store the encryption key to simulate it was dynamically generated
    storage = await async_get_encryption_key_storage(hass)
    await storage.async_store_key(
        mock_config_entry.unique_id, mock_config_entry.data[CONF_NOISE_PSK]
    )

    mock_client.noise_encryption_set_key = AsyncMock(return_value=False)

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.connect.assert_called_once()
    mock_client.noise_encryption_set_key.assert_called_once_with(b"")
    mock_client.disconnect.assert_called_once()

    assert (
        await storage.async_get_key(mock_config_entry.unique_id)
        == mock_config_entry.data[CONF_NOISE_PSK]
    )


@pytest.mark.usefixtures("mock_zeroconf")
async def test_serial_port_scanner(
    hass: HomeAssistant,
    mock_client,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """ESPHome serial proxies are exposed as `esphome://` USB serial ports.

    Three entries cover the auth variants the scanner cares about: no auth,
    noise PSK only, and password only.
    """
    noise_psk = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="

    # Device without authentication
    open_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Open ESP",
        data={CONF_HOST: "10.0.0.1", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    open_entry.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        entry=open_entry,
        device_info={
            "mac_address": "11:22:33:44:55:AA",
            "manufacturer": "Espressif",
            "serial_proxies": [SerialProxyInfo(name="uart0", port_type=0)],
        },
    )

    # Device using Noise
    noise_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Noise ESP",
        data={
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_NOISE_PSK: noise_psk,
        },
    )
    noise_entry.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        entry=noise_entry,
        device_info={
            "mac_address": "11:22:33:44:55:AA",
            "manufacturer": "Espressif",
            "serial_proxies": [SerialProxyInfo(name="uart0", port_type=0)],
        },
    )

    # Device using a password
    password_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Password ESP",
        data={CONF_HOST: "10.0.0.3", CONF_PORT: 6053, CONF_PASSWORD: "secret"},
    )
    password_entry.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        entry=password_entry,
        device_info={
            "mac_address": "11:22:33:44:55:AA",
            "manufacturer": "Espressif",
            "serial_proxies": [
                SerialProxyInfo(name="uart0", port_type=0),
                SerialProxyInfo(name="uart1", port_type=0),
            ],
        },
    )

    # All three entries share the module-scoped `mock_client`, so give each its
    # own lightweight client so the URL host/port match the entry's config.
    open_entry.runtime_data.client = Mock(connected_address="10.0.0.1", port=6053)
    noise_entry.runtime_data.client = Mock(connected_address="10.0.0.2", port=6053)
    password_entry.runtime_data.client = Mock(connected_address="10.0.0.3", port=6053)

    ports = await async_scan_serial_ports(hass)
    esphome_ports = [p for p in ports if p.device.startswith("esphome://")]

    assert esphome_ports == [
        SerialDevice(
            device="esphome://10.0.0.1:6053/?port_name=uart0",
            serial_number="11:22:33:44:55:AA-0",
            manufacturer="Espressif",
            description="Open ESP (uart0)",
        ),
        SerialDevice(
            device=f"esphome://10.0.0.2:6053/?port_name=uart0&key={quote(noise_psk, safe='')}",
            serial_number="11:22:33:44:55:AA-0",
            manufacturer="Espressif",
            description="Noise ESP (uart0)",
        ),
        SerialDevice(
            device="esphome://10.0.0.3:6053/?port_name=uart0&password=secret",
            serial_number="11:22:33:44:55:AA-0",
            manufacturer="Espressif",
            description="Password ESP (uart0)",
        ),
        SerialDevice(
            device="esphome://10.0.0.3:6053/?port_name=uart1&password=secret",
            serial_number="11:22:33:44:55:AA-1",
            manufacturer="Espressif",
            description="Password ESP (uart1)",
        ),
    ]


@pytest.mark.usefixtures("mock_zeroconf")
async def test_serial_port_scanner_unavailable(
    hass: HomeAssistant,
    mock_client,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Disconnected ESPHome entries do not contribute serial ports."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "serial_proxies": [SerialProxyInfo(name="uart0", port_type=0)],
        },
    )
    device.entry.runtime_data.client = Mock(connected_address="10.0.0.1", port=6053)

    # The device normally shows up
    ports = await async_scan_serial_ports(hass)
    assert [p for p in ports if p.device.startswith("esphome://")] != []

    # But not when it's unavailable
    device.entry.runtime_data.available = False

    ports = await async_scan_serial_ports(hass)
    assert [p for p in ports if p.device.startswith("esphome://")] == []


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_connection_error(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that connection error during key clearing does not remove key from storage."""
    # Store the encryption key to simulate it was dynamically generated
    storage = await async_get_encryption_key_storage(hass)
    await storage.async_store_key(
        mock_config_entry.unique_id, mock_config_entry.data[CONF_NOISE_PSK]
    )

    mock_client.connect = AsyncMock(side_effect=APIConnectionError("Connection failed"))

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.connect.assert_called_once()
    mock_client.disconnect.assert_called_once()

    assert (
        await storage.async_get_key(mock_config_entry.unique_id)
        == mock_config_entry.data[CONF_NOISE_PSK]
    )
