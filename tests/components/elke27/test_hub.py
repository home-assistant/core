"""Tests for the Elke27 hub."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from elke27_lib import LinkKeys

from homeassistant.components.elke27.const import READY_TIMEOUT
from homeassistant.components.elke27.hub import Elke27Hub
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


def _client_factory(client: AsyncMock) -> callable:
    def _factory(*args, **kwargs):
        assert not kwargs
        assert len(args) == 1
        return client

    return _factory


async def test_connect_subscribes_and_disconnects(hass: HomeAssistant) -> None:
    """Test hub connect subscribes and disconnects cleanly."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.async_discover = AsyncMock(
        return_value=[SimpleNamespace(panel_name="Panel A")]
    )
    client._coerce_identity = lambda identity: identity
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    unsubscribe = Mock()
    client.subscribe = Mock(return_value=unsubscribe)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        hub = Elke27Hub(
            hass,
            "192.168.1.70",
            2101,
            LinkKeys("tk", "lk", "lh").to_json(),
            "112233445566",
            None,
            None,
        )
        await hub.async_connect()

    client.async_connect.assert_awaited_once()
    client.wait_ready.assert_awaited_once_with(timeout_s=READY_TIMEOUT)
    client.subscribe.assert_called_once()

    await hub.async_disconnect()
    unsubscribe.assert_called_once()
    client.async_disconnect.assert_awaited_once()


async def test_connect_wait_ready_false_disconnects(
    hass: HomeAssistant,
) -> None:
    """Test hub connect disconnects when ready is false."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.async_discover = AsyncMock(return_value=[])
    client._coerce_identity = lambda identity: identity
    client.wait_ready = AsyncMock(return_value=False)
    client.async_disconnect = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        hub = Elke27Hub(
            hass,
            "192.168.1.71",
            2101,
            LinkKeys("tk", "lk", "lh").to_json(),
            "112233445566",
            None,
            None,
        )
        with pytest.raises(ConfigEntryNotReady):
            await hub.async_connect()

    client.async_disconnect.assert_awaited_once()
