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
    ("discovery_side_effect", "discovery_return_value"),
    [
        (DaliGatewayError("Discovery failed"), None),
        (None, []),
    ],
    ids=["rediscovery_fails", "gateway_not_found"],
)
async def test_setup_entry_connection_failure_scenarios(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    discovery_side_effect: Exception | None,
    discovery_return_value: list | None,
) -> None:
    """Test setup fails when gateway connection fails and rediscovery fails."""
    mock_config_entry.add_to_hass(hass)
    mock_gateway.connect.side_effect = DaliGatewayError("Connection failed")

    with patch(
        "homeassistant.components.sunricher_dali.DaliGatewayDiscovery"
    ) as mock_discovery_class:
        mock_discovery = mock_discovery_class.return_value
        if discovery_side_effect:
            mock_discovery.discover_gateways = AsyncMock(
                side_effect=discovery_side_effect
            )
        else:
            mock_discovery.discover_gateways = AsyncMock(
                return_value=discovery_return_value
            )

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
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
    new_ip: str,
    reconnect_succeeds: bool,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup when gateway IP changes with different reconnection outcomes."""
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
            "homeassistant.components.sunricher_dali.DaliGatewayDiscovery"
        ) as mock_discovery_class,
        patch(
            "homeassistant.components.sunricher_dali.DaliGateway"
        ) as mock_gateway_class,
    ):
        mock_discovery = mock_discovery_class.return_value
        mock_discovery.discover_gateways = AsyncMock(return_value=[new_gateway])

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
