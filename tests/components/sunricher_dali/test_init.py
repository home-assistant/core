"""Test the Sunricher DALI integration initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

from PySrDaliGateway.exceptions import DaliGatewayError

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


async def test_setup_entry_connection_error_rediscovery_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test setup fails when gateway connection fails and rediscovery also fails."""
    mock_config_entry.add_to_hass(hass)
    mock_gateway.connect.side_effect = DaliGatewayError("Connection failed")

    with patch(
        "homeassistant.components.sunricher_dali.DaliGatewayDiscovery"
    ) as mock_discovery_class:
        mock_discovery = mock_discovery_class.return_value
        mock_discovery.discover_gateways = AsyncMock(
            side_effect=DaliGatewayError("Discovery failed")
        )

        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gateway.connect.assert_called_once()


async def test_setup_entry_connection_error_gateway_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test setup fails when gateway not found during rediscovery."""
    mock_config_entry.add_to_hass(hass)
    mock_gateway.connect.side_effect = DaliGatewayError("Connection failed")

    with patch(
        "homeassistant.components.sunricher_dali.DaliGatewayDiscovery"
    ) as mock_discovery_class:
        mock_discovery = mock_discovery_class.return_value
        mock_discovery.discover_gateways = AsyncMock(return_value=[])

        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gateway.connect.assert_called_once()
    mock_discovery.discover_gateways.assert_called_once_with("6A242121110E")


async def test_setup_entry_ip_changed_successful_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
) -> None:
    """Test successful setup when gateway IP changes and reconnection succeeds."""
    mock_config_entry.add_to_hass(hass)

    new_gateway = MagicMock()
    new_gateway.gw_sn = "6A242121110E"
    new_gateway.gw_ip = "192.168.1.200"
    new_gateway.port = 1883
    new_gateway.name = "Test Gateway"
    new_gateway.connect = AsyncMock()
    new_gateway.disconnect = AsyncMock()
    new_gateway.discover_devices = AsyncMock(return_value=mock_devices)

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

        mock_gateway.connect.side_effect = DaliGatewayError("Connection failed")
        mock_gateway_class.side_effect = [mock_gateway, new_gateway]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    mock_gateway.connect.assert_called_once()
    new_gateway.connect.assert_called_once()
    new_gateway.discover_devices.assert_called_once()


async def test_setup_entry_same_ip_retry_succeeds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
) -> None:
    """Test successful retry when gateway temporarily unavailable but recovers."""
    mock_config_entry.add_to_hass(hass)

    discovered_gateway = MagicMock()
    discovered_gateway.gw_sn = "6A242121110E"
    discovered_gateway.gw_ip = "192.168.1.100"

    with patch(
        "homeassistant.components.sunricher_dali.DaliGatewayDiscovery"
    ) as mock_discovery_class:
        mock_discovery = mock_discovery_class.return_value
        mock_discovery.discover_gateways = AsyncMock(return_value=[discovered_gateway])

        call_count = 0

        def connect_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DaliGatewayError("Temporary network issue")

        mock_gateway.connect.side_effect = connect_side_effect

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"
    assert mock_gateway.connect.call_count == 2


async def test_setup_entry_same_ip_retry_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test setup fails when gateway at same IP cannot connect even after retry."""
    mock_config_entry.add_to_hass(hass)

    discovered_gateway = MagicMock()
    discovered_gateway.gw_sn = "6A242121110E"
    discovered_gateway.gw_ip = "192.168.1.100"

    with patch(
        "homeassistant.components.sunricher_dali.DaliGatewayDiscovery"
    ) as mock_discovery_class:
        mock_discovery = mock_discovery_class.return_value
        mock_discovery.discover_gateways = AsyncMock(return_value=[discovered_gateway])
        mock_gateway.connect.side_effect = DaliGatewayError("Connection failed")

        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"
    assert mock_gateway.connect.call_count == 2


async def test_setup_entry_ip_changed_reconnect_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test setup fails when IP changes but reconnection to new IP fails."""
    mock_config_entry.add_to_hass(hass)

    new_gateway = MagicMock()
    new_gateway.gw_sn = "6A242121110E"
    new_gateway.gw_ip = "192.168.1.200"
    new_gateway.connect = AsyncMock(side_effect=DaliGatewayError("Connection failed"))

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

        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    mock_gateway.connect.assert_called_once()
    new_gateway.connect.assert_called_once()


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
