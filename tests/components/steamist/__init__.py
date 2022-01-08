"""Tests for the Steamist integration."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from aiosteamist import Steamist, SteamistStatus

from homeassistant.components import steamist
from homeassistant.components.steamist.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_ASYNC_GET_STATUS_INACTIVE = SteamistStatus(
    temp=70, temp_units="F", minutes_remain=0, active=False
)
MOCK_ASYNC_GET_STATUS_ACTIVE = SteamistStatus(
    temp=102, temp_units="F", minutes_remain=14, active=True
)


async def _async_setup_entry_with_status(
    hass: HomeAssistant, status: SteamistStatus
) -> tuple[Steamist, ConfigEntry]:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    config_entry.add_to_hass(hass)
    client = _mocked_steamist()
    client.async_get_status = AsyncMock(return_value=status)
    with _patch_status(status, client):
        await async_setup_component(hass, steamist.DOMAIN, {steamist.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED
    return client, config_entry


def _mocked_steamist() -> Steamist:
    client = MagicMock(auto_spec=Steamist)
    client.async_turn_on_steam = AsyncMock()
    client.async_turn_off_steam = AsyncMock()
    client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_ACTIVE)
    return client


def _patch_status(status: SteamistStatus, client: Steamist | None = None):
    if client is None:
        client = _mocked_steamist()
        client.async_get_status = AsyncMock(return_value=status)

    @contextmanager
    def _patcher():
        with patch("homeassistant.components.steamist.Steamist", return_value=client):
            yield

    return _patcher()
