"""Test the UniFi Protect setup flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from uiprotect import NotAuthorized, NvrError, ProtectApiClient
from uiprotect.api import DEVICE_UPDATE_INTERVAL
from uiprotect.data import NVR, Bootstrap, CloudAccount, Light

from homeassistant.components.unifiprotect.const import (
    AUTH_RETRIES,
    CONF_DISABLE_RTSP,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import _patch_discovery
from .utils import MockUFPFixture, init_entry, time_changed

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_setup(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac


async def test_setup_multiple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    bootstrap: Bootstrap,
) -> None:
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac

    nvr = bootstrap.nvr
    nvr._api = ufp.api
    nvr.mac = "A1E00C826983"
    ufp.api.get_nvr = AsyncMock(return_value=nvr)

    with patch(
        "homeassistant.components.unifiprotect.utils.ProtectApiClient"
    ) as mock_api:
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

        assert mock_config.state is ConfigEntryState.LOADED
        assert ufp.api.update.called
        assert mock_config.unique_id == ufp.api.bootstrap.nvr.mac


async def test_reload(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test updating entry reload entry."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.LOADED

    options = dict(ufp.entry.options)
    options[CONF_DISABLE_RTSP] = True
    hass.config_entries.async_update_entry(ufp.entry, options=options)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.LOADED
    assert ufp.api.async_disconnect_ws.called


async def test_unload(hass: HomeAssistant, ufp: MockUFPFixture, light: Light) -> None:
    """Test unloading of unifiprotect entry."""

    await init_entry(hass, ufp, [light])
    assert ufp.entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(ufp.entry.entry_id)
    assert ufp.entry.state is ConfigEntryState.NOT_LOADED
    assert ufp.api.async_disconnect_ws.called


async def test_setup_too_old(
    hass: HomeAssistant, ufp: MockUFPFixture, old_nvr: NVR
) -> None:
    """Test setup of unifiprotect entry with too old of version of UniFi Protect."""

    old_bootstrap = ufp.api.bootstrap.copy()
    old_bootstrap.nvr = old_nvr
    ufp.api.update.return_value = old_bootstrap
    ufp.api.bootstrap = old_bootstrap

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_cloud_account(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    cloud_account: CloudAccount,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test setup of unifiprotect entry with cloud account."""

    bootstrap = ufp.api.bootstrap
    user = bootstrap.users[bootstrap.auth_user_id]
    user.cloud_account = cloud_account
    bootstrap.users[bootstrap.auth_user_id] = user
    ufp.api.get_bootstrap.return_value = bootstrap
    ws_client = await hass_ws_client(hass)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.LOADED

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "cloud_user":
            issue = i
    assert issue is not None


async def test_setup_failed_update(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test setup of unifiprotect entry with failed update."""

    ufp.api.update = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.SETUP_RETRY
    assert ufp.api.update.called


async def test_setup_failed_update_reauth(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test setup of unifiprotect entry with update that gives unauthroized error."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.LOADED

    # reauth should not be triggered until there are 10 auth failures in a row
    # to verify it is not transient
    ufp.api.update = AsyncMock(side_effect=NotAuthorized)
    for _ in range(AUTH_RETRIES):
        await time_changed(hass, DEVICE_UPDATE_INTERVAL)
        assert len(hass.config_entries.flow._progress) == 0

    assert ufp.api.update.call_count == AUTH_RETRIES
    assert ufp.entry.state is ConfigEntryState.LOADED

    await time_changed(hass, DEVICE_UPDATE_INTERVAL)
    assert ufp.api.update.call_count == AUTH_RETRIES + 1
    assert len(hass.config_entries.flow._progress) == 1


async def test_setup_failed_error(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test setup of unifiprotect entry with generic error."""

    ufp.api.update = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failed_auth(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test setup of unifiprotect entry with unauthorized error after multiple retries."""

    ufp.api.update = AsyncMock(side_effect=NotAuthorized)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    assert ufp.entry.state is ConfigEntryState.SETUP_RETRY

    for _ in range(AUTH_RETRIES - 1):
        await hass.config_entries.async_reload(ufp.entry.entry_id)
        assert ufp.entry.state is ConfigEntryState.SETUP_RETRY

    await hass.config_entries.async_reload(ufp.entry.entry_id)
    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_starts_discovery(
    hass: HomeAssistant, ufp_config_entry: ConfigEntry, ufp_client: ProtectApiClient
) -> None:
    """Test setting up will start discovery."""
    with (
        _patch_discovery(),
        patch(
            "homeassistant.components.unifiprotect.utils.ProtectApiClient"
        ) as mock_api,
    ):
        ufp_config_entry.add_to_hass(hass)
        mock_api.return_value = ufp_client
        ufp = MockUFPFixture(ufp_config_entry, ufp_client)

        await hass.config_entries.async_setup(ufp.entry.entry_id)
        await hass.async_block_till_done()
        assert ufp.entry.state is ConfigEntryState.LOADED
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1


async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""

    await init_entry(hass, ufp, [light])
    assert await async_setup_component(hass, "config", {})
    entity_id = "light.test_light"
    entry_id = ufp.entry.entry_id

    entity = entity_registry.async_get(entity_id)
    assert entity is not None

    live_device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(live_device_entry.id, entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "e9:88:e7:b8:b4:40")},
    )
    response = await client.remove_device(dead_device_entry.id, entry_id)
    assert response["success"]


async def test_device_remove_devices_nvr(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a NVR device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    entry_id = ufp.entry.entry_id

    live_device_entry = list(device_registry.devices.values())[0]
    client = await hass_ws_client(hass)
    response = await client.remove_device(live_device_entry.id, entry_id)
    assert not response["success"]
