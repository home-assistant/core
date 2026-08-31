"""Tests for device-initiated outgoing connections."""

from unittest.mock import AsyncMock, MagicMock, patch

from aioesphomeapi import APIClient
import pytest

from homeassistant.components.esphome.const import (
    CONF_ALLOW_OUTGOING_CONNECTION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDeviceType

from tests.common import MockConfigEntry

MAC = "11:22:33:44:55:aa"


def _make_entry(*, options: dict | None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        options=options or {},
        unique_id=MAC,
    )


@pytest.fixture
def mock_server() -> MagicMock:
    """Patch the aioesphomeapi listener class in the singleton module."""
    server = MagicMock()
    server.start = AsyncMock()
    server.stop = AsyncMock()
    server.register = MagicMock(return_value=MagicMock())
    with patch(
        "homeassistant.components.esphome.outgoing_connection.OutgoingConnectionServer",
        return_value=server,
    ):
        yield server


async def test_outgoing_connection_registration(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """Enabling the option registers the device MAC with the shared listener."""
    entry = _make_entry(options={CONF_ALLOW_OUTGOING_CONNECTION: True})
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    mock_server.start.assert_awaited_once()
    assert mock_server.register.call_count == 1
    assert mock_server.register.call_args.args[0] == MAC
    # The client declares itself a dial-back target in its hello
    assert mock_client.outgoing_connection_target is True

    unregister = mock_server.register.return_value
    unregister.assert_not_called()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    unregister.assert_called()


async def test_outgoing_connection_disabled(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """An explicitly disabled entry registers nothing and does not set the flag."""
    entry = _make_entry(options={CONF_ALLOW_OUTGOING_CONNECTION: False})
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    mock_server.register.assert_not_called()
    assert mock_client.outgoing_connection_target is False


async def test_outgoing_connection_auto_enables_on_supported_device(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """The option turns on and sticks when a device first advertises support."""
    entry = _make_entry(options=None)
    entry.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        entry=entry,
        device_info={"api_outgoing_connection_supported": True},
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_ALLOW_OUTGOING_CONNECTION] is True
    # The scheduled reload re-created the client with the flag and registered
    assert mock_client.outgoing_connection_target is True
    assert mock_server.register.call_count == 1


async def test_outgoing_connection_not_auto_enabled_without_support(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """A device without the capability leaves the option untouched."""
    entry = _make_entry(options=None)
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    assert CONF_ALLOW_OUTGOING_CONNECTION not in entry.options
    mock_server.register.assert_not_called()


async def test_outgoing_connection_listener_unavailable(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """Setup continues when the listener port cannot be bound."""
    mock_server.start.side_effect = OSError("address in use")
    entry = _make_entry(options={CONF_ALLOW_OUTGOING_CONNECTION: True})
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_server.register.assert_not_called()
