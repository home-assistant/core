"""Tests for the Elke27 integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from elke27_lib import LinkKeys
from elke27_lib.errors import Elke27TimeoutError

from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_calls_connect_disconnect_and_subscribe(
    hass: HomeAssistant,
) -> None:
    """Test setup/unload uses hub and coordinator lifecycle."""
    hub = AsyncMock()
    hub.panel_name = None
    hub.async_connect = AsyncMock(return_value=None)
    hub.async_disconnect = AsyncMock(return_value=None)

    coordinator = AsyncMock()
    coordinator.async_start = AsyncMock(return_value=None)
    coordinator.async_refresh_now = AsyncMock(return_value=None)
    coordinator.async_stop = AsyncMock(return_value=None)
    coordinator.data = None

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.Elke27Hub", return_value=hub
    ), patch(
        "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
        return_value=coordinator,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        hub.async_connect.assert_awaited_once()
        coordinator.async_start.assert_awaited_once()
        coordinator.async_refresh_now.assert_awaited_once()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    coordinator.async_stop.assert_awaited_once()
    hub.async_disconnect.assert_awaited_once()


async def test_setup_transient_error_returns_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test transient setup errors return not ready."""
    hub = AsyncMock()
    hub.panel_name = None
    hub.async_connect = AsyncMock(side_effect=Elke27TimeoutError())
    hub.async_disconnect = AsyncMock(return_value=None)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.12",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.Elke27Hub", return_value=hub
    ), patch(
        "homeassistant.components.elke27.Elke27DataUpdateCoordinator"
    ) as coordinator_cls:
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator_cls.assert_not_called()
    hub.async_disconnect.assert_awaited_once()
