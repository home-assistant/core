"""Tests for the Lyngdorf integration."""

from unittest.mock import MagicMock, patch

from lyngdorf import LyngdorfModel
import pytest

from homeassistant.components.lyngdorf.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MODEL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionError("Connection failed"),
        OSError("Network unreachable"),
        TimeoutError("Connection timeout"),
    ],
    ids=["connection_error", "os_error", "timeout"],
)
async def test_setup_entry_connection_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    exc: Exception,
) -> None:
    """Test setup retries when connecting to the receiver fails."""
    mock_config_entry.add_to_hass(hass)
    mock_receiver.connect.side_effect = exc

    with patch(
        "homeassistant.components.lyngdorf.lookup_model",
        return_value=LyngdorfModel.MP_60,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_receiver_disconnects_on_hass_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test the receiver is disconnected when Home Assistant stops."""
    assert init_integration.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_receiver.disconnect.assert_awaited_once()


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unloading the config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_uses_the_home_assistant_websession(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_create_receiver: MagicMock,
) -> None:
    """Test the receiver is given Home Assistant's shared aiohttp session."""
    assert mock_create_receiver.call_args.kwargs["session"] is async_get_clientsession(
        hass
    )


async def test_unload_releases_receiver_subscriptions(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test every receiver subscription is released when the entry unloads."""
    unsubscribe = mock_receiver.on_change.return_value
    registered = mock_receiver.on_change.call_count
    assert registered > 0
    assert unsubscribe.call_count == 0

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert unsubscribe.call_count == registered


async def test_zone_b_via_device_id(
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that Zone B's via_device_id points at the main device."""
    assert init_integration.unique_id
    main_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.unique_id), init_integration.entry_id
    )
    zone_b_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{init_integration.unique_id}_zone_b"), init_integration.entry_id
    )
    assert main_device is not None
    assert zone_b_device is not None
    assert zone_b_device.via_device_id == main_device.id


@pytest.mark.parametrize(
    ("serial", "expected_mac_connections"),
    [
        ("0050c27c76b2", {"00:50:c2:7c:76:b2"}),
        ("NOT-A-MAC", set()),
    ],
    ids=["valid_mac", "non_mac_serial"],
)
@pytest.mark.usefixtures("mock_receiver")
async def test_mac_connection_registered_when_serial_is_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    serial: str,
    expected_mac_connections: set[str],
) -> None:
    """Test that the device gets a MAC connection only when serial parses as one."""
    entry = MockConfigEntry(
        title="Mock Lyngdorf",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_MODEL: "MP-60",
            CONF_SERIAL_NUMBER: serial,
        },
        unique_id=serial.lower(),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lyngdorf.lookup_model",
        return_value=LyngdorfModel.MP_60,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, serial.lower()), entry.entry_id
    )
    assert device is not None
    mac_connections = {
        value for kind, value in device.connections if kind == dr.CONNECTION_NETWORK_MAC
    }
    assert mac_connections == expected_mac_connections


async def test_no_zone_b_device_for_model_without_zone_b(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test no Zone B device is created for a model without Zone B."""
    mock_config_entry.add_to_hass(hass)
    mock_receiver.zone_b = None

    with patch(
        "homeassistant.components.lyngdorf.lookup_model",
        return_value=LyngdorfModel.TDAI_3400,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.unique_id}_zone_b"), mock_config_entry.entry_id
    )
    assert device is None
