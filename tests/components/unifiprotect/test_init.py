"""Test the UniFi Protect setup flow."""
# pylint: disable=protected-access
from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

import aiohttp
from pyunifiprotect import NotAuthorized, NvrError, ProtectApiClient
from pyunifiprotect.data import NVR, Bootstrap, Light

from homeassistant.components.unifiprotect.const import (
    CONF_DISABLE_RTSP,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import _patch_discovery
from .utils import MockUFPFixture, init_entry, time_changed

from tests.common import MockConfigEntry


async def remove_device(
    ws_client: aiohttp.ClientWebSocketResponse, device_id: str, config_entry_id: str
) -> bool:
    """Remove config entry from a device."""
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry_id,
            "device_id": device_id,
        }
    )
    response = await ws_client.receive_json()
    return response["success"]


async def test_setup(hass: HomeAssistant, ufp: MockUFPFixture):
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state == ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac


async def test_setup_multiple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    bootstrap: Bootstrap,
):
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state == ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac

    nvr = bootstrap.nvr
    nvr._api = ufp.api
    nvr.mac = "A1E00C826983"
    nvr.id
    ufp.api.get_nvr = AsyncMock(return_value=nvr)

    with patch("homeassistant.components.unifiprotect.ProtectApiClient") as mock_api:
        mock_config = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "id": "UnifiProtect",
                "port": 443,
                "verify_ssl": False,
            },
            version=2,
        )
        mock_config.add_to_hass(hass)

        mock_api.return_value = ufp.api

        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()

        assert mock_config.state == ConfigEntryState.LOADED
        assert ufp.api.update.called
        assert mock_config.unique_id == ufp.api.bootstrap.nvr.mac


async def test_reload(hass: HomeAssistant, ufp: MockUFPFixture):
    """Test updating entry reload entry."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state == ConfigEntryState.LOADED

    options = dict(ufp.entry.options)
    options[CONF_DISABLE_RTSP] = True
    hass.config_entries.async_update_entry(ufp.entry, options=options)
    await hass.async_block_till_done()

    assert ufp.entry.state == ConfigEntryState.LOADED
    assert ufp.api.async_disconnect_ws.called


async def test_unload(hass: HomeAssistant, ufp: MockUFPFixture, light: Light):
    """Test unloading of unifiprotect entry."""

    await init_entry(hass, ufp, [light])
    assert ufp.entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(ufp.entry.entry_id)
    assert ufp.entry.state == ConfigEntryState.NOT_LOADED
    assert ufp.api.async_disconnect_ws.called


async def test_setup_too_old(hass: HomeAssistant, ufp: MockUFPFixture, old_nvr: NVR):
    """Test setup of unifiprotect entry with too old of version of UniFi Protect."""

    ufp.api.get_nvr.return_value = old_nvr

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state == ConfigEntryState.SETUP_ERROR
    assert not ufp.api.update.called


async def test_setup_failed_update(hass: HomeAssistant, ufp: MockUFPFixture):
    """Test setup of unifiprotect entry with failed update."""

    ufp.api.update = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state == ConfigEntryState.SETUP_RETRY
    assert ufp.api.update.called


async def test_setup_failed_update_reauth(hass: HomeAssistant, ufp: MockUFPFixture):
    """Test setup of unifiprotect entry with update that gives unauthroized error."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state == ConfigEntryState.LOADED

    # reauth should not be triggered until there are 10 auth failures in a row
    # to verify it is not transient
    ufp.api.update = AsyncMock(side_effect=NotAuthorized)
    for _ in range(10):
        await time_changed(hass, DEFAULT_SCAN_INTERVAL)
        assert len(hass.config_entries.flow._progress) == 0

    assert ufp.api.update.call_count == 10
    assert ufp.entry.state == ConfigEntryState.LOADED

    await time_changed(hass, DEFAULT_SCAN_INTERVAL)
    assert ufp.api.update.call_count == 11
    assert len(hass.config_entries.flow._progress) == 1


async def test_setup_failed_error(hass: HomeAssistant, ufp: MockUFPFixture):
    """Test setup of unifiprotect entry with generic error."""

    ufp.api.get_nvr = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state == ConfigEntryState.SETUP_RETRY
    assert not ufp.api.update.called


async def test_setup_failed_auth(hass: HomeAssistant, ufp: MockUFPFixture):
    """Test setup of unifiprotect entry with unauthorized error."""

    ufp.api.get_nvr = AsyncMock(side_effect=NotAuthorized)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    assert ufp.entry.state == ConfigEntryState.SETUP_ERROR
    assert not ufp.api.update.called


async def test_setup_starts_discovery(
    hass: HomeAssistant, ufp_config_entry: ConfigEntry, ufp_client: ProtectApiClient
):
    """Test setting up will start discovery."""
    with _patch_discovery(), patch(
        "homeassistant.components.unifiprotect.ProtectApiClient"
    ) as mock_api:
        ufp_config_entry.add_to_hass(hass)
        mock_api.return_value = ufp_client
        ufp = MockUFPFixture(ufp_config_entry, ufp_client)

        await hass.config_entries.async_setup(ufp.entry.entry_id)
        await hass.async_block_till_done()
        assert ufp.entry.state == ConfigEntryState.LOADED
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1


async def test_device_remove_devices(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[aiohttp.ClientWebSocketResponse]
    ],
) -> None:
    """Test we can only remove a device that no longer exists."""

    await init_entry(hass, ufp, [light])
    assert await async_setup_component(hass, "config", {})
    entity_id = "light.test_light"
    entry_id = ufp.entry.entry_id

    registry: er.EntityRegistry = er.async_get(hass)
    entity = registry.async_get(entity_id)
    assert entity is not None
    device_registry = dr.async_get(hass)

    live_device_entry = device_registry.async_get(entity.device_id)
    assert (
        await remove_device(await hass_ws_client(hass), live_device_entry.id, entry_id)
        is False
    )

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "e9:88:e7:b8:b4:40")},
    )
    assert (
        await remove_device(await hass_ws_client(hass), dead_device_entry.id, entry_id)
        is True
    )


async def test_device_remove_devices_nvr(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[aiohttp.ClientWebSocketResponse]
    ],
) -> None:
    """Test we can only remove a NVR device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    entry_id = ufp.entry.entry_id

    device_registry = dr.async_get(hass)

    live_device_entry = list(device_registry.devices.values())[0]
    assert (
        await remove_device(await hass_ws_client(hass), live_device_entry.id, entry_id)
        is False
    )
