"""Tests for the opnsense integration setup."""

from unittest import mock

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseSSLError,
    OPNsenseTimeoutError,
    OPNsenseUnknownFirmware,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.opnsense.const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .const import ARP


@pytest.mark.parametrize(
    ("exc", "expected_state", "expected_translation_key"),
    [
        (OPNsenseUnknownFirmware, ConfigEntryState.SETUP_ERROR, "unknown_firmware"),
        (OPNsenseBelowMinFirmware, ConfigEntryState.SETUP_ERROR, "firmware_too_old"),
        (OPNsenseInvalidURL, ConfigEntryState.SETUP_ERROR, "invalid_url"),
        (OPNsenseTimeoutError, ConfigEntryState.SETUP_RETRY, "timeout_connecting"),
        (OPNsenseSSLError, ConfigEntryState.SETUP_ERROR, "ssl_error"),
        (OPNsenseInvalidAuth, ConfigEntryState.SETUP_ERROR, "invalid_auth"),
        (OPNsensePrivilegeMissing, ConfigEntryState.SETUP_ERROR, "privilege_missing"),
        (OPNsenseConnectionError, ConfigEntryState.SETUP_RETRY, "cannot_connect"),
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: mock.AsyncMock,
    exc: type[Exception],
    expected_state: ConfigEntryState,
    expected_translation_key: str,
) -> None:
    """Test async_setup_entry surfaces translation-keyed errors."""
    mock_opnsense_client.validate.side_effect = exc

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    assert mock_config_entry.error_reason_translation_key == expected_translation_key
    assert mock_config_entry.error_reason_translation_placeholders == {
        "url": mock_config_entry.data[CONF_URL]
    }


async def test_setup_entry_tracker_interface_not_found(
    hass: HomeAssistant,
    mock_opnsense_client: mock.AsyncMock,
) -> None:
    """Test async_setup_entry rejects unknown tracker interfaces."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://router.lan/api",
            CONF_API_KEY: "key",
            CONF_API_SECRET: "secret",
            CONF_VERIFY_SSL: False,
            CONF_TRACKER_INTERFACES: ["NOPE"],
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "tracker_interface_not_found"
    assert entry.error_reason_translation_placeholders == {
        "interface": "NOPE",
        "known": "WAN, LAN",
    }


STALE_MAC = "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("mac", "removable"),
    [
        pytest.param(ARP[0]["mac"], False, id="connected"),
        pytest.param(STALE_MAC, True, id="stale"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mac: str,
    removable: bool,
) -> None:
    """Test only client devices which are not connected can be removed."""
    # A client device left over from before the router stopped reporting it
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, STALE_MAC)},
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})

    connection = (dr.CONNECTION_NETWORK_MAC, mac)
    device = device_registry.async_get_device_by_connection(
        connection, mock_config_entry.entry_id
    )
    assert device is not None
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(device.id)

    assert response["success"] is removable
    assert (
        device_registry.async_get_device_by_connection(
            connection, mock_config_entry.entry_id
        )
        is None
    ) is removable


async def test_remove_config_entry_device_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: mock.AsyncMock,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test client devices can be removed while the entry is not loaded."""
    mock_opnsense_client.validate.side_effect = OPNsenseConnectionError
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, ARP[0]["mac"])},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert await async_setup_component(hass, "config", {})

    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(device.id)

    assert response["success"]
    assert device_registry.async_get(device.id) is None


async def test_remove_departed_client_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: mock.AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a departed client's device is removable and re-created on reconnect."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    mac = ARP[1]["mac"]
    connection = (dr.CONNECTION_NETWORK_MAC, mac)

    mock_opnsense_client.get_arp_table.return_value = [ARP[0]]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_connection(
        connection, mock_config_entry.entry_id
    )
    assert device is not None
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(device.id)
    assert response["success"]
    assert (
        device_registry.async_get_device_by_connection(
            connection, mock_config_entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac) is None
    )

    mock_opnsense_client.get_arp_table.return_value = ARP
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_connection(
        connection, mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Desktop"
    assert (
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac)
        is not None
    )
