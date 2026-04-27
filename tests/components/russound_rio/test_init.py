"""Tests for the Russound RIO integration."""

from unittest.mock import AsyncMock, Mock

from aiorussound import RussoundTcpConnectionHandler
from aiorussound.connection import RussoundSerialConnectionHandler
from aiorussound.rio.models import CallbackType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.russound_rio.const import CONF_BAUDRATE, DOMAIN, TYPE_TCP
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import mock_state_update, setup_integration
from .const import MOCK_SERIAL_CONFIG, MOCK_TCP_CONFIG, MODEL

from tests.common import MockConfigEntry


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test the Cambridge Audio configuration entry not ready."""
    mock_russound_client.connect.side_effect = TimeoutError
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_russound_client.connect = AsyncMock(return_value=True)


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_disconnect_reconnect_log(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)

    mock_russound_client.is_connected = Mock(return_value=False)
    await mock_state_update(mock_russound_client, CallbackType.CONNECTION)
    assert "Disconnected from device at 192.168.20.75" in caplog.text

    mock_russound_client.is_connected = Mock(return_value=True)
    await mock_state_update(mock_russound_client, CallbackType.CONNECTION)
    assert "Reconnected to device at 192.168.20.75" in caplog.text


async def test_migrate_entry_from_v1_to_v2_on_setup(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a version 1 entry is migrated during setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_HOST: "192.168.20.75",
            CONF_PORT: 9621,
        },
        unique_id="00:11:22:33:44:55",
        title=MODEL,
    )
    await setup_integration(hass, entry)

    assert entry.version == 2
    assert entry.data == {
        CONF_TYPE: TYPE_TCP,
        CONF_HOST: "192.168.20.75",
        CONF_PORT: 9621,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_migrate_entry_from_future_version_fails_on_setup(
    hass: HomeAssistant,
) -> None:
    """Test setup fails for a future config entry version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data={
            CONF_TYPE: TYPE_TCP,
            CONF_HOST: "192.168.20.75",
            CONF_PORT: 9621,
        },
        unique_id="00:11:22:33:44:55",
        title=MODEL,
    )
    await setup_integration(hass, entry)

    assert entry.version == 3


async def test_setup_entry_uses_tcp_handler(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup uses the TCP handler."""
    await setup_integration(hass, mock_config_entry)

    handler = mock_russound_client.connection_handler
    assert isinstance(handler, RussoundTcpConnectionHandler)
    assert handler.host == MOCK_TCP_CONFIG[CONF_HOST]
    assert handler.port == MOCK_TCP_CONFIG[CONF_PORT]


async def test_setup_entry_uses_serial_handler(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_serial_config_entry: MockConfigEntry,
) -> None:
    """Test setup uses the serial handler."""
    await setup_integration(hass, mock_serial_config_entry)

    handler = mock_russound_client.connection_handler
    assert isinstance(handler, RussoundSerialConnectionHandler)
    assert handler.port == MOCK_SERIAL_CONFIG[CONF_DEVICE]
    assert handler.baudrate == MOCK_SERIAL_CONFIG[CONF_BAUDRATE]
