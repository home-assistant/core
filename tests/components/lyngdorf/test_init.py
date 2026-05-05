"""Tests for the Lyngdorf integration."""

from unittest.mock import MagicMock, patch

from lyngdorf.const import LyngdorfModel
import pytest

from homeassistant.components.lyngdorf.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
    mock_receiver.async_connect.side_effect = exc

    with patch(
        "homeassistant.components.lyngdorf.lookup_receiver_model",
        return_value=LyngdorfModel.MP_60,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unloading the config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("serial", "expected_mac"),
    [
        ("0050c27c76b2", "00:50:c2:7c:76:b2"),
        ("NOT-A-MAC", None),
    ],
    ids=["valid_mac", "non_mac_serial"],
)
async def test_mac_connection_registered_when_serial_is_mac(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    device_registry: dr.DeviceRegistry,
    serial: str,
    expected_mac: str | None,
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
        unique_id=serial,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lyngdorf.lookup_receiver_model",
        return_value=LyngdorfModel.MP_60,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, serial)})
    assert device is not None
    mac_connections = {
        value for kind, value in device.connections if kind == dr.CONNECTION_NETWORK_MAC
    }
    if expected_mac is None:
        assert mac_connections == set()
    else:
        assert mac_connections == {expected_mac}
