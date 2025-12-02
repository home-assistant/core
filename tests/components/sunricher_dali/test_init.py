"""Test the Sunricher DALI integration initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

from PySrDaliGateway.exceptions import DaliGatewayError
import pytest

from homeassistant.components.sunricher_dali.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_gateway.connect.assert_called_once()


@pytest.mark.parametrize(
    "dhcp_data_available",
    [False, True],
    ids=["no_mac_stored", "mac_stored_no_dhcp_data"],
)
async def test_setup_entry_connection_failure_scenarios(
    hass: HomeAssistant,
    mock_gateway: MagicMock,
    dhcp_data_available: bool,
) -> None:
    """Test setup fails when gateway connection fails and DHCP lookup fails."""
    # Create config entry with MAC if needed
    config_data = {
        "serial_number": "6A242121110E",
        "host": "192.168.1.100",
        "port": 1883,
        "name": "Test Gateway",
        "username": "gateway_user",
        "password": "gateway_pass",
    }
    if dhcp_data_available:
        config_data["mac"] = "aa:bb:cc:dd:ee:ff"

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        unique_id="6A242121110E",
        title="Test Gateway",
    )
    mock_config_entry.add_to_hass(hass)
    mock_gateway.connect.side_effect = DaliGatewayError("Connection failed")

    with patch(
        "homeassistant.components.sunricher_dali.dhcp_helpers.async_get_address_data_internal",
        return_value={},  # Empty DHCP data - no IP found
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gateway.connect.assert_called_once()


@pytest.mark.parametrize(
    ("new_ip", "reconnect_succeeds", "expected_state"),
    [
        ("192.168.1.200", True, ConfigEntryState.LOADED),
        ("192.168.1.200", False, ConfigEntryState.SETUP_RETRY),
    ],
    ids=["ip_changed_reconnect_succeeds", "ip_changed_reconnect_fails"],
)
async def test_setup_entry_ip_change_scenarios(
    hass: HomeAssistant,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
    new_ip: str,
    reconnect_succeeds: bool,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup when gateway IP changes via DHCP with different reconnection outcomes."""
    # Create config entry with MAC address
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "serial_number": "6A242121110E",
            "host": "192.168.1.100",
            "port": 1883,
            "name": "Test Gateway",
            "username": "gateway_user",
            "password": "gateway_pass",
            "mac": "aa:bb:cc:dd:ee:ff",
        },
        unique_id="6A242121110E",
        title="Test Gateway",
    )
    mock_config_entry.add_to_hass(hass)

    new_gateway = MagicMock()
    new_gateway.gw_sn = "6A242121110E"
    new_gateway.gw_ip = new_ip
    new_gateway.port = 1883
    new_gateway.name = "Test Gateway"
    new_gateway.disconnect = AsyncMock()
    new_gateway.discover_devices = AsyncMock(return_value=mock_devices)

    if reconnect_succeeds:
        new_gateway.connect = AsyncMock()
    else:
        new_gateway.connect = AsyncMock(
            side_effect=DaliGatewayError("Connection failed")
        )

    with (
        patch(
            "homeassistant.components.sunricher_dali.dhcp_helpers.async_get_address_data_internal",
            return_value={"aa:bb:cc:dd:ee:ff": {"ip": new_ip, "hostname": "gateway"}},
        ),
        patch(
            "homeassistant.components.sunricher_dali.DaliGateway"
        ) as mock_gateway_class,
    ):
        mock_gateway.connect.side_effect = DaliGatewayError("Initial connection failed")
        mock_gateway_class.side_effect = [mock_gateway, new_gateway]

        setup_result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert setup_result is reconnect_succeeds
    assert mock_config_entry.state is expected_state
    assert mock_config_entry.data[CONF_HOST] == new_ip
    mock_gateway.connect.assert_called_once()
    new_gateway.connect.assert_called_once()
    if reconnect_succeeds:
        new_gateway.discover_devices.assert_called_once()


async def test_setup_entry_discovery_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test setup fails when device discovery fails."""
    mock_config_entry.add_to_hass(hass)
    mock_gateway.discover_devices.side_effect = DaliGatewayError("Discovery failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gateway.connect.assert_called_once()
    mock_gateway.discover_devices.assert_called_once()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test successful unloading of config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_remove_stale_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
) -> None:
    """Test stale devices are removed when device list decreases."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices_before = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    initial_count = len(devices_before)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_gateway.discover_devices.return_value = mock_devices[:2]

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    devices_after = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices_after) < initial_count

    gateway_device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_gateway.gw_sn)}
    )
    assert gateway_device is not None
    assert mock_config_entry.entry_id in gateway_device.config_entries
