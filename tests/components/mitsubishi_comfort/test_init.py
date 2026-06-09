"""Tests for the Mitsubishi Comfort integration setup."""

from unittest.mock import AsyncMock, MagicMock

from mitsubishi_comfort import DeviceInfo
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import pytest

from homeassistant.components.mitsubishi_comfort.const import (
    CONF_ADDRESSES,
    CONF_CREDENTIALS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_ADDRESS, MOCK_MAC, MOCK_PASSWORD, MOCK_SERIAL, MOCK_USERNAME

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get_entity_id("climate", DOMAIN, "SERIAL001")


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (AuthenticationError("bad creds"), ConfigEntryState.SETUP_ERROR),
        (DeviceConnectionError("Connection refused"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_login_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup translates login failures into the expected config entry state."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_account.login.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_setup_entry_no_devices_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Test setup raises a setup error when no devices are found."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_account.discover_devices.return_value = {}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_no_address_loads_and_registers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_cloud_account: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with no known LAN address loads and registers the device.

    The cloud returns each device's credentials but never its LAN IP. Without a
    resolved address the device cannot be polled, so it creates no entity — but
    it is registered with its MAC so "registered_devices" DHCP discovery can
    supply the IP and reload the entry. Setup must not retry (which would hammer
    the cloud API) since retrying can never resolve the address. The missing
    address is surfaced with a warning rather than failing silently.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        unique_id="user-12345",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(MOCK_MAC))}
    )
    assert "No local IP address is known" in caplog.text


async def test_setup_entry_caches_and_replays_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test credentials are replayed to discovery and persisted on the entry."""
    mock_account, _ = mock_setup_integration
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Discovery is told to reuse cached credentials so it can skip Socket.IO.
    assert "cached_credentials" in mock_account.discover_devices.call_args.kwargs
    # The discovered credentials are persisted for the next setup.
    assert mock_config_entry.data[CONF_CREDENTIALS] == {
        MOCK_SERIAL: {
            "password": "dGVzdHBhc3M=",
            "crypto_serial": "0102030405060708090a",
            "mac": MOCK_MAC,
        }
    }


async def test_setup_entry_resolves_address_from_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test the LAN address is injected from the entry's persisted cache.

    The cloud-discovered device carries no address; the entity is only created
    because the entry holds a previously resolved address for the device's MAC.
    """
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get_entity_id("climate", DOMAIN, "SERIAL001")
    assert mock_config_entry.data[CONF_ADDRESSES][dr.format_mac(MOCK_MAC)] == (
        MOCK_ADDRESS
    )


async def test_setup_entry_skips_incomplete_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test setup skips incomplete devices and creates complete ones."""
    incomplete_info = DeviceInfo(
        serial="SERIAL002",
        label="Bedroom",
        address="",
        mac="11:22:33:44:55:66",
        unit_type="ductless",
        password="",
        crypto_serial="",
    )
    mock_account, _ = mock_setup_integration
    mock_account.discover_devices.return_value = {
        "SERIAL001": mock_device_info,
        "SERIAL002": incomplete_info,
    }
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get_entity_id("climate", DOMAIN, "SERIAL001")
    assert entity_registry.async_get_entity_id("climate", DOMAIN, "SERIAL002") is None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
