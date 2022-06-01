"""Test the UniFi Protect setup flow."""
# pylint: disable=protected-access
from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

import aiohttp
from pyunifiprotect import NotAuthorized, NvrError
from pyunifiprotect.data import NVR, Light

from homeassistant.components.unifiprotect.const import CONF_DISABLE_RTSP, DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import _patch_discovery
from .conftest import MockBootstrap, MockEntityFixture

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


async def test_setup(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac


async def test_setup_multiple(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_client,
    mock_bootstrap: MockBootstrap,
):
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    nvr = mock_bootstrap.nvr
    nvr._api = mock_client
    nvr.mac = "A1E00C826983"
    nvr.id
    mock_client.get_nvr = AsyncMock(return_value=nvr)

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

        mock_api.return_value = mock_client

        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()

        assert mock_config.state == ConfigEntryState.LOADED
        assert mock_client.update.called
        assert mock_config.unique_id == mock_client.bootstrap.nvr.mac


async def test_reload(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test updating entry reload entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.LOADED

    options = dict(mock_entry.entry.options)
    options[CONF_DISABLE_RTSP] = True
    hass.config_entries.async_update_entry(mock_entry.entry, options=options)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.async_disconnect_ws.called


async def test_unload(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test unloading of unifiprotect entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_entry.entry.entry_id)
    assert mock_entry.entry.state == ConfigEntryState.NOT_LOADED
    assert mock_entry.api.async_disconnect_ws.called


async def test_setup_too_old(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_old_nvr: NVR
):
    """Test setup of unifiprotect entry with too old of version of UniFi Protect."""

    mock_entry.api.get_nvr.return_value = mock_old_nvr

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.SETUP_ERROR
    assert not mock_entry.api.update.called


async def test_setup_failed_update(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test setup of unifiprotect entry with failed update."""

    mock_entry.api.update = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.SETUP_RETRY
    assert mock_entry.api.update.called


async def test_setup_failed_update_reauth(
    hass: HomeAssistant, mock_entry: MockEntityFixture
):
    """Test setup of unifiprotect entry with update that gives unauthroized error."""

    mock_entry.api.update = AsyncMock(side_effect=NotAuthorized)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.SETUP_RETRY
    assert mock_entry.api.update.called


async def test_setup_failed_error(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test setup of unifiprotect entry with generic error."""

    mock_entry.api.get_nvr = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.SETUP_RETRY
    assert not mock_entry.api.update.called


async def test_setup_failed_auth(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test setup of unifiprotect entry with unauthorized error."""

    mock_entry.api.get_nvr = AsyncMock(side_effect=NotAuthorized)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    assert mock_entry.entry.state == ConfigEntryState.SETUP_ERROR
    assert not mock_entry.api.update.called


async def test_setup_starts_discovery(
    hass: HomeAssistant, mock_ufp_config_entry: ConfigEntry, mock_client
):
    """Test setting up will start discovery."""
    with _patch_discovery(), patch(
        "homeassistant.components.unifiprotect.ProtectApiClient"
    ) as mock_api:
        mock_ufp_config_entry.add_to_hass(hass)
        mock_api.return_value = mock_client
        mock_entry = MockEntityFixture(mock_ufp_config_entry, mock_client)

        await hass.config_entries.async_setup(mock_entry.entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.entry.state == ConfigEntryState.LOADED
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1


async def test_migrate_reboot_button(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Test migrating unique ID of reboot button."""

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    light1.id = "lightid1"

    light2 = mock_light.copy()
    light2._api = mock_entry.api
    light2.name = "Test Light 2"
    light2.id = "lightid2"
    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
        light2.id: light2,
    }
    mock_entry.api.get_bootstrap = AsyncMock(return_value=mock_entry.api.bootstrap)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON, DOMAIN, light1.id, config_entry=mock_entry.entry
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light2.id}_reboot",
        config_entry=mock_entry.entry,
    )

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    buttons = []
    for entity in er.async_entries_for_config_entry(
        registry, mock_entry.entry.entry_id
    ):
        if entity.domain == Platform.BUTTON.value:
            buttons.append(entity)
            print(entity.entity_id)
    assert len(buttons) == 2

    assert registry.async_get(f"{Platform.BUTTON}.test_light_1_reboot_device") is None
    assert registry.async_get(f"{Platform.BUTTON}.test_light_1_reboot_device_2") is None
    light = registry.async_get(f"{Platform.BUTTON}.unifiprotect_lightid1")
    assert light is not None
    assert light.unique_id == f"{light1.id}_reboot"

    assert registry.async_get(f"{Platform.BUTTON}.test_light_2_reboot_device") is None
    assert registry.async_get(f"{Platform.BUTTON}.test_light_2_reboot_device_2") is None
    light = registry.async_get(f"{Platform.BUTTON}.unifiprotect_lightid2_reboot")
    assert light is not None
    assert light.unique_id == f"{light2.id}_reboot"


async def test_migrate_reboot_button_no_device(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Test migrating unique ID of reboot button if UniFi Protect device ID changed."""

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    light1.id = "lightid1"

    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
    }
    mock_entry.api.get_bootstrap = AsyncMock(return_value=mock_entry.api.bootstrap)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON, DOMAIN, "lightid2", config_entry=mock_entry.entry
    )

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    buttons = []
    for entity in er.async_entries_for_config_entry(
        registry, mock_entry.entry.entry_id
    ):
        if entity.domain == Platform.BUTTON.value:
            buttons.append(entity)
    assert len(buttons) == 2

    light = registry.async_get(f"{Platform.BUTTON}.unifiprotect_lightid2")
    assert light is not None
    assert light.unique_id == "lightid2"


async def test_migrate_reboot_button_fail(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Test migrating unique ID of reboot button."""

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    light1.id = "lightid1"

    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
    }
    mock_entry.api.get_bootstrap = AsyncMock(return_value=mock_entry.api.bootstrap)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        light1.id,
        config_entry=mock_entry.entry,
        suggested_object_id=light1.name,
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light1.id}_reboot",
        config_entry=mock_entry.entry,
        suggested_object_id=light1.name,
    )

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    light = registry.async_get(f"{Platform.BUTTON}.test_light_1")
    assert light is not None
    assert light.unique_id == f"{light1.id}"


async def test_device_remove_devices(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_light: Light,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[aiohttp.ClientWebSocketResponse]
    ],
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    light1.id = "lightid1"
    light1.mac = "AABBCCDDEEFF"

    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
    }
    mock_entry.api.get_bootstrap = AsyncMock(return_value=mock_entry.api.bootstrap)
    light_entity_id = "light.test_light_1"
    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    entry_id = mock_entry.entry.entry_id

    registry: er.EntityRegistry = er.async_get(hass)
    entity = registry.entities[light_entity_id]
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
