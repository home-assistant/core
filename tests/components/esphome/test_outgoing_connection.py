"""Tests for device-initiated outgoing connections."""

from unittest.mock import AsyncMock, MagicMock, patch

from aioesphomeapi import APIClient

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


def _make_entry(*, allow_outgoing: bool) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        options={CONF_ALLOW_OUTGOING_CONNECTION: allow_outgoing},
        unique_id=MAC,
    )


async def test_outgoing_connection_registration(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Enabling the option registers the device MAC with the shared listener."""
    entry = _make_entry(allow_outgoing=True)
    entry.add_to_hass(hass)
    server = MagicMock()
    unregister = MagicMock()
    server.register.return_value = unregister
    with patch(
        "homeassistant.components.esphome.manager._async_get_outgoing_connection_server",
        new=AsyncMock(return_value=server),
    ):
        await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
        await hass.async_block_till_done()

    assert server.register.call_count == 1
    assert server.register.call_args.args[0] == MAC
    unregister.assert_not_called()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    unregister.assert_called_once()


async def test_outgoing_connection_disabled_by_default(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Without the option nothing is registered."""
    entry = _make_entry(allow_outgoing=False)
    entry.add_to_hass(hass)
    server = MagicMock()
    with patch(
        "homeassistant.components.esphome.manager._async_get_outgoing_connection_server",
        new=AsyncMock(return_value=server),
    ):
        await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
        await hass.async_block_till_done()

    server.register.assert_not_called()


async def test_outgoing_connection_listener_unavailable(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Setup continues when the listener port cannot be bound."""
    entry = _make_entry(allow_outgoing=True)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.esphome.manager._async_get_outgoing_connection_server",
        new=AsyncMock(side_effect=OSError("address in use")),
    ):
        await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
