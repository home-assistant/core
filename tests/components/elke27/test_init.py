"""Tests for the Elke27 integration setup."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch

import pytest

_client_module = ModuleType("elke27_lib.client")
_client_module.Elke27Client = object
_client_module.Result = object
_package_module = ModuleType("elke27_lib")
_package_module.client = _client_module
sys.modules.setdefault("elke27_lib", _package_module)
sys.modules.setdefault("elke27_lib.client", _client_module)

from homeassistant.components.elke27.const import DEFAULT_PORT, DOMAIN, READY_TIMEOUT
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _mock_elke27_lib(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a minimal elke27_lib stub for import-time safety."""
    client_module = ModuleType("elke27_lib.client")
    client_module.Elke27Client = object
    client_module.Result = object
    package_module = ModuleType("elke27_lib")
    package_module.client = client_module
    monkeypatch.setitem(sys.modules, "elke27_lib", package_module)
    monkeypatch.setitem(sys.modules, "elke27_lib.client", client_module)


async def test_setup_unload_calls_start_stop_and_subscribe(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test client start/stop and event subscription lifecycle."""
    _mock_elke27_lib(monkeypatch)
    client = AsyncMock()
    client.is_ready = True
    unsubscribe = Mock()
    client.subscribe = Mock(return_value=unsubscribe)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.10", CONF_PORT: DEFAULT_PORT},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client", return_value=client
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        client.start.assert_awaited_once()
        client.subscribe.assert_called_once()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    unsubscribe.assert_called_once()
    client.stop.assert_awaited_once()


async def test_setup_waits_for_ready(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test readiness gating is invoked when the client is not ready."""
    _mock_elke27_lib(monkeypatch)
    client = AsyncMock()
    client.is_ready = False

    async def _wait_ready(*, timeout_s: int) -> None:
        client.is_ready = True

    client.wait_ready = AsyncMock(side_effect=_wait_ready)
    client.subscribe = Mock(return_value=Mock())

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.11", CONF_PORT: DEFAULT_PORT},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client", return_value=client
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client.wait_ready.assert_awaited_once_with(timeout_s=READY_TIMEOUT)


async def test_setup_failure_stops_client(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test setup failure cleans up the client."""
    _mock_elke27_lib(monkeypatch)
    client = AsyncMock()
    client.start.side_effect = TimeoutError
    client.subscribe = Mock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.12", CONF_PORT: DEFAULT_PORT},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client", return_value=client
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client.stop.assert_awaited_once()
