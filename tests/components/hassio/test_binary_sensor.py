"""The tests for the hassio binary sensors."""

from dataclasses import replace
from datetime import timedelta
import os
from unittest.mock import AsyncMock, patch

from aiohasupervisor.models.mounts import CIFSMountResponse, MountsInfo, MountState
import pytest

from homeassistant.components.hassio import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import MOCK_REPOSITORIES, MOCK_STORE_ADDONS

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(
    aioclient_mock: AiohttpClientMocker,
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_changelog: AsyncMock,
    addon_stats: AsyncMock,
    resolution_info: AsyncMock,
) -> None:
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {
                "supervisor": "222",
                "homeassistant": "0.110.0",
                "hassos": "1.2.3",
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "data": {
                    "chassis": "vm",
                    "operating_system": "Debian GNU/Linux 10 (buster)",
                    "kernel": "4.19.0-6-amd64",
                },
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0", "version": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={
            "result": "ok",
            "data": {
                "version_latest": "1.0.0",
                "version": "1.0.0",
                "update_available": False,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "version": "1.0.0",
                "version_latest": "1.0.0",
                "auto_update": True,
                "addons": [
                    {
                        "name": "test",
                        "state": "started",
                        "slug": "test",
                        "installed": True,
                        "update_available": True,
                        "version": "2.0.0",
                        "version_latest": "2.0.1",
                        "repository": "core",
                        "url": "https://github.com/home-assistant/addons/test",
                        "icon": False,
                    },
                    {
                        "name": "test2",
                        "state": "stopped",
                        "slug": "test2",
                        "installed": True,
                        "update_available": False,
                        "version": "3.1.0",
                        "version_latest": "3.1.0",
                        "repository": "core",
                        "url": "https://github.com",
                        "icon": False,
                    },
                ],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )
    aioclient_mock.get(
        "http://127.0.0.1/network/info",
        json={
            "result": "ok",
            "data": {
                "host_internet": True,
                "supervisor_internet": True,
            },
        },
    )


@pytest.mark.parametrize(
    ("store_addons", "store_repositories"), [(MOCK_STORE_ADDONS, MOCK_REPOSITORIES)]
)
@pytest.mark.parametrize(
    ("entity_id", "expected", "addon_state"),
    [
        ("binary_sensor.test_running", "on", "started"),
        ("binary_sensor.test2_running", "off", "stopped"),
    ],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    entity_id: str,
    expected: str,
    addon_state: str,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    addon_installed: AsyncMock,
) -> None:
    """Test hassio OS and addons binary sensor."""
    addon_installed.return_value.state = addon_state
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    # Verify that the entity is disabled by default.
    assert hass.states.get(entity_id) is None

    # Enable the entity.
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify that the entity have the expected state.
    state = hass.states.get(entity_id)
    assert state.state == expected


async def test_mount_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    supervisor_client: AsyncMock,
) -> None:
    """Test hassio mounts binary sensor."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    entity_id = "binary_sensor.nas_connected"

    # Verify that the entity doesn't exist.
    assert hass.states.get(entity_id) is None

    # Add a mount.
    mock_mounts = [
        CIFSMountResponse(
            share="files",
            server="1.2.3.4",
            name="NAS",
            type="cifs",
            usage="share",
            read_only=False,
            state=MountState.ACTIVE,
            user_path="/share/nas",
        )
    ]
    supervisor_client.mounts.info = AsyncMock(
        return_value=MountsInfo(default_backup_mount=None, mounts=mock_mounts)
    )

    # Let it reload.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1000))
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify that the entity is disabled by default.
    assert hass.states.get(entity_id) is None

    # Enable the entity.
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test new entity.
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "on"

    # Change state and test again.
    mock_mounts[0] = replace(mock_mounts[0], state=MountState.FAILED)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1000))
    await hass.async_block_till_done(wait_background_tasks=True)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "off"

    # Remove mount and test again.
    mount = mock_mounts.pop()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1000))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id) is None

    # Recreate mount with the same name.
    mock_mounts.append(mount)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1000))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id) is not None
