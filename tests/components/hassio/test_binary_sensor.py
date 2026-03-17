"""The tests for the hassio binary sensors."""

from dataclasses import replace
from datetime import timedelta
import os
from pathlib import PurePath
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from aiohasupervisor.models import AddonState, InstalledAddonComplete
from aiohasupervisor.models.mounts import (
    CIFSMountResponse,
    MountsInfo,
    MountState,
    MountType,
    MountUsage,
    NFSMountResponse,
)
import pytest

from homeassistant.components.hassio import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import MOCK_REPOSITORIES, MOCK_STORE_ADDONS

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(
    aioclient_mock: AiohttpClientMocker,
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_changelog: AsyncMock,
    addon_stats: AsyncMock,
    resolution_info: AsyncMock,
    jobs_info: AsyncMock,
    host_info: AsyncMock,
    supervisor_root_info: AsyncMock,
    homeassistant_info: AsyncMock,
    supervisor_info: AsyncMock,
    addons_list: AsyncMock,
    network_info: AsyncMock,
    os_info: AsyncMock,
    homeassistant_stats: AsyncMock,
    supervisor_stats: AsyncMock,
) -> None:
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )

    def mock_addon_info(slug: str):
        addon = Mock(
            spec=InstalledAddonComplete,
            to_dict=addon_installed.return_value.to_dict,
            **addon_installed.return_value.to_dict(),
        )
        if slug == "test":
            addon.name = "test"
            addon.slug = "test"
            addon.version = "2.0.0"
            addon.version_latest = "2.0.1"
            addon.update_available = True
            addon.state = AddonState.STARTED
            addon.url = "https://github.com/home-assistant/addons/test"
            addon.auto_update = True
        else:
            addon.name = "test2"
            addon.slug = "test2"
            addon.version = "3.1.0"
            addon.version_latest = "3.1.0"
            addon.update_available = False
            addon.state = AddonState.STOPPED
            addon.url = "https://github.com"
            addon.auto_update = False

        return addon

    addon_installed.side_effect = mock_addon_info


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
    mock_mounts: list[CIFSMountResponse | NFSMountResponse] = [
        CIFSMountResponse(
            share="files",
            server="1.2.3.4",
            name="NAS",
            type=MountType.CIFS,
            usage=MountUsage.SHARE,
            read_only=False,
            state=MountState.ACTIVE,
            user_path=PurePath("/share/nas"),
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


async def test_mount_refresh_after_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test hassio mount state is refreshed after an issue was send by the supervisor."""
    # Add a mount.
    mock_mounts: list[CIFSMountResponse | NFSMountResponse] = [
        CIFSMountResponse(
            share="files",
            server="1.2.3.4",
            name="NAS",
            type=MountType.CIFS,
            usage=MountUsage.SHARE,
            read_only=False,
            state=MountState.ACTIVE,
            user_path=PurePath("/share/nas"),
        )
    ]
    supervisor_client.mounts.info = AsyncMock(
        return_value=MountsInfo(default_backup_mount=None, mounts=mock_mounts)
    )

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

    # Enable the entity.
    entity_id = "binary_sensor.nas_connected"
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test new entity.
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "on"

    # Change mount state to failed, issue a repair, and verify entity's state.
    mock_mounts[0] = replace(mock_mounts[0], state=MountState.FAILED)
    client = await hass_ws_client(hass)
    issue_uuid = uuid4().hex
    await client.send_json(
        {
            "id": 1,
            "type": "supervisor/event",
            "data": {
                "event": "issue_changed",
                "data": {
                    "uuid": issue_uuid,
                    "type": "mount_failed",
                    "context": "mount",
                    "reference": "nas",
                    "suggestions": [
                        {
                            "uuid": uuid4().hex,
                            "type": "execute_reload",
                            "context": "mount",
                            "reference": "nas",
                        },
                        {
                            "uuid": uuid4().hex,
                            "type": "execute_remove",
                            "context": "mount",
                            "reference": "nas",
                        },
                    ],
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "off"

    # Change mount state to active, issue a repair, and verify entity's state.
    mock_mounts[0] = replace(mock_mounts[0], state=MountState.ACTIVE)
    await client.send_json(
        {
            "id": 2,
            "type": "supervisor/event",
            "data": {
                "event": "issue_removed",
                "data": {
                    "uuid": issue_uuid,
                    "type": "mount_failed",
                    "context": "mount",
                    "reference": "nas",
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "on"
