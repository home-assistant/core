"""Tests for the Elke27 integration setup."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock, patch

from elke27_lib.errors import Elke27TimeoutError

from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
    READY_TIMEOUT,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _client_factory(client: AsyncMock) -> callable:
    def _factory(*args, **kwargs):
        assert not kwargs
        assert len(args) == 1
        return client

    return _factory


async def test_setup_unload_calls_connect_disconnect_and_subscribe(
    hass: HomeAssistant,
) -> None:
    """Test client connect/disconnect and event subscription lifecycle."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.async_discover = AsyncMock(return_value=[])
    client.wait_ready = AsyncMock(return_value=True)
    unsubscribe = Mock()
    client.subscribe = Mock(return_value=unsubscribe)
    client.async_disconnect = AsyncMock(return_value=None)
    client.snapshot = object()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: "link-keys-json",
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        client.async_connect.assert_awaited_once()
        client.wait_ready.assert_awaited_once_with(timeout_s=READY_TIMEOUT)
        client.subscribe.assert_called_once()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    unsubscribe.assert_called_once()
    client.async_disconnect.assert_awaited_once()


async def test_setup_transient_error_returns_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test transient setup errors return not ready."""
    client = AsyncMock()
    client.async_connect = AsyncMock(side_effect=Elke27TimeoutError)
    client.async_disconnect = AsyncMock(return_value=None)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.12",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: "link-keys-json",
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client.async_disconnect.assert_awaited_once()
