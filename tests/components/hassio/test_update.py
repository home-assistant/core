"""The tests for the hassio update entities."""

from datetime import timedelta
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohasupervisor import (
    SupervisorBadRequestError,
    SupervisorError,
    SupervisorNotFoundError,
)
from aiohasupervisor.models import (
    HomeAssistantUpdateOptions,
    OSUpdate,
    StoreAddonUpdate,
)
import pytest

from homeassistant.components.backup import BackupManagerError, ManagerBackup

# pylint: disable-next=hass-component-root-import
from homeassistant.components.backup.manager import AgentBackupStatus
from homeassistant.components.hassio import DOMAIN
from homeassistant.components.hassio.const import REQUEST_REFRESH_DELAY
from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(
    aioclient_mock: AiohttpClientMocker,
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_stats: AsyncMock,
    addon_changelog: AsyncMock,
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
        json={
            "result": "ok",
            "data": {"version_latest": "1.0.0dev222", "version": "1.0.0dev221"},
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={
            "result": "ok",
            "data": {
                "version_latest": "1.0.0dev2222",
                "version": "1.0.0dev2221",
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
                "version_latest": "1.0.1dev222",
                "auto_update": True,
                "addons": [
                    {
                        "name": "test",
                        "state": "started",
                        "slug": "test",
                        "installed": True,
                        "update_available": True,
                        "icon": False,
                        "version": "2.0.0",
                        "version_latest": "2.0.1",
                        "repository": "core",
                        "url": "https://github.com/home-assistant/addons/test",
                    },
                    {
                        "name": "test2",
                        "state": "stopped",
                        "slug": "test2",
                        "installed": True,
                        "update_available": False,
                        "icon": True,
                        "version": "3.1.0",
                        "version_latest": "3.1.0",
                        "repository": "core",
                        "url": "https://github.com",
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
    ("entity_id", "expected_state", "auto_update"),
    [
        ("update.home_assistant_operating_system_update", "on", False),
        ("update.home_assistant_supervisor_update", "on", True),
        ("update.home_assistant_core_update", "on", False),
        ("update.test_update", "on", True),
        ("update.test2_update", "off", False),
    ],
)
async def test_update_entities(
    hass: HomeAssistant,
    entity_id,
    expected_state,
    auto_update,
    aioclient_mock: AiohttpClientMocker,
    addon_installed: AsyncMock,
) -> None:
    """Test update entities."""
    addon_installed.return_value.auto_update = auto_update
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

    # Verify that the entity have the expected state.
    state = hass.states.get(entity_id)
    assert state.state == expected_state

    # Verify that the auto_update attribute is correct
    assert state.attributes["auto_update"] is auto_update


async def test_update_addon(hass: HomeAssistant, update_addon: AsyncMock) -> None:
    """Test updating addon update entity."""
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

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
    ) as mock_create_backup:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.test_update"},
            blocking=True,
        )
    mock_create_backup.assert_not_called()
    update_addon.assert_called_once_with("test", StoreAddonUpdate(backup=False))


async def setup_backup_integration(hass: HomeAssistant) -> None:
    """Set up the backup integration."""
    async_initialize_backup(hass)
    assert await async_setup_component(hass, "backup", {})
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("commands", "default_mount", "expected_kwargs"),
    [
        (
            [],
            None,
            {
                "agent_ids": ["hassio.local"],
                "extra_metadata": {"supervisor.addon_update": "test"},
                "include_addons": ["test"],
                "include_all_addons": False,
                "include_database": False,
                "include_folders": None,
                "include_homeassistant": False,
                "name": "test 2.0.0",
                "password": None,
            },
        ),
        (
            [],
            "my_nas",
            {
                "agent_ids": ["hassio.my_nas"],
                "extra_metadata": {"supervisor.addon_update": "test"},
                "include_addons": ["test"],
                "include_all_addons": False,
                "include_database": False,
                "include_folders": None,
                "include_homeassistant": False,
                "name": "test 2.0.0",
                "password": None,
            },
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {
                        "agent_ids": ["test-agent"],
                        "include_addons": ["my-addon"],
                        "include_all_addons": True,
                        "include_database": False,
                        "include_folders": ["share"],
                        "name": "cool_backup",
                        "password": "hunter2",
                    },
                },
            ],
            None,
            {
                "agent_ids": ["hassio.local"],
                "extra_metadata": {"supervisor.addon_update": "test"},
                "include_addons": ["test"],
                "include_all_addons": False,
                "include_database": False,
                "include_folders": None,
                "include_homeassistant": False,
                "name": "test 2.0.0",
                "password": "hunter2",
            },
        ),
    ],
)
async def test_update_addon_with_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    update_addon: AsyncMock,
    commands: list[dict[str, Any]],
    default_mount: str | None,
    expected_kwargs: dict[str, Any],
) -> None:
    """Test updating addon update entity."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await setup_backup_integration(hass)

    client = await hass_ws_client(hass)
    for command in commands:
        await client.send_json_auto_id(command)
        result = await client.receive_json()
        assert result["success"]

    supervisor_client.mounts.info.return_value.default_backup_mount = default_mount
    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
    ) as mock_create_backup:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.test_update", "backup": True},
            blocking=True,
        )
    mock_create_backup.assert_called_once_with(**expected_kwargs)
    update_addon.assert_called_once_with("test", StoreAddonUpdate(backup=False))


@pytest.mark.parametrize(
    ("backups", "removed_backups"),
    [
        (
            {},
            [],
        ),
        (
            {
                "backup-1": MagicMock(
                    agents={"hassio.local": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"hassio.local": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"hassio.local": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    extra_metadata={"supervisor.addon_update": "other"},
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"hassio.local": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    extra_metadata={"supervisor.addon_update": "other"},
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-5": MagicMock(
                    agents={"hassio.local": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    extra_metadata={"supervisor.addon_update": "test"},
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-6": MagicMock(
                    agents={"hassio.local": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    extra_metadata={"supervisor.addon_update": "test"},
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
            },
            ["backup-5"],
        ),
    ],
)
async def test_update_addon_with_backup_removes_old_backups(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    update_addon: AsyncMock,
    backups: dict[str, ManagerBackup],
    removed_backups: list[str],
) -> None:
    """Test updating addon update entity."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await setup_backup_integration(hass)

    supervisor_client.mounts.info.return_value.default_backup_mount = None
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_create_backup",
        ) as mock_create_backup,
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_delete_backup",
            autospec=True,
            return_value={},
        ) as async_delete_backup,
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backups",
            return_value=(backups, {}),
        ),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.test_update", "backup": True},
            blocking=True,
        )
    mock_create_backup.assert_called_once_with(
        agent_ids=["hassio.local"],
        extra_metadata={"supervisor.addon_update": "test"},
        include_addons=["test"],
        include_all_addons=False,
        include_database=False,
        include_folders=None,
        include_homeassistant=False,
        name="test 2.0.0",
        password=None,
    )
    assert len(async_delete_backup.mock_calls) == len(removed_backups)
    for call in async_delete_backup.mock_calls:
        assert call.args[1] in removed_backups
    update_addon.assert_called_once_with("test", StoreAddonUpdate(backup=False))


async def test_update_os(hass: HomeAssistant, supervisor_client: AsyncMock) -> None:
    """Test updating OS update entity."""
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

    supervisor_client.os.update.return_value = None
    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
    ) as mock_create_backup:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_operating_system_update"},
            blocking=True,
        )
    mock_create_backup.assert_not_called()
    supervisor_client.os.update.assert_called_once_with(OSUpdate(version=None))


@pytest.mark.parametrize(
    ("commands", "default_mount", "expected_kwargs"),
    [
        (
            [],
            None,
            {
                "agent_ids": ["hassio.local"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": f"Home Assistant Core {HAVERSION}",
                "password": None,
            },
        ),
        (
            [],
            "my_nas",
            {
                "agent_ids": ["hassio.my_nas"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": f"Home Assistant Core {HAVERSION}",
                "password": None,
            },
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {
                        "agent_ids": ["test-agent"],
                        "include_addons": ["my-addon"],
                        "include_all_addons": True,
                        "include_database": False,
                        "include_folders": ["share"],
                        "name": "cool_backup",
                        "password": "hunter2",
                    },
                },
            ],
            None,
            {
                "agent_ids": ["test-agent"],
                "include_addons": ["my-addon"],
                "include_all_addons": True,
                "include_database": False,
                "include_folders": ["share"],
                "include_homeassistant": True,
                "name": "cool_backup",
                "password": "hunter2",
                "with_automatic_settings": True,
            },
        ),
    ],
)
async def test_update_os_with_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    commands: list[dict[str, Any]],
    default_mount: str | None,
    expected_kwargs: dict[str, Any],
) -> None:
    """Test updating OS update entity."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await setup_backup_integration(hass)

    client = await hass_ws_client(hass)
    for command in commands:
        await client.send_json_auto_id(command)
        result = await client.receive_json()
        assert result["success"]

    supervisor_client.os.update.return_value = None
    supervisor_client.mounts.info.return_value.default_backup_mount = default_mount
    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
    ) as mock_create_backup:
        await hass.services.async_call(
            "update",
            "install",
            {
                "entity_id": "update.home_assistant_operating_system_update",
                "backup": True,
            },
            blocking=True,
        )
    mock_create_backup.assert_called_once_with(**expected_kwargs)
    supervisor_client.os.update.assert_called_once_with(OSUpdate(version=None))


async def test_update_core(hass: HomeAssistant, supervisor_client: AsyncMock) -> None:
    """Test updating core update entity."""
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

    supervisor_client.homeassistant.update.return_value = None
    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
    ) as mock_create_backup:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_core_update"},
            blocking=True,
        )
    mock_create_backup.assert_not_called()
    supervisor_client.homeassistant.update.assert_called_once_with(
        HomeAssistantUpdateOptions(version=None, backup=False)
    )


@pytest.mark.parametrize(
    ("commands", "default_mount", "expected_kwargs"),
    [
        (
            [],
            None,
            {
                "agent_ids": ["hassio.local"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": f"Home Assistant Core {HAVERSION}",
                "password": None,
            },
        ),
        (
            [],
            "my_nas",
            {
                "agent_ids": ["hassio.my_nas"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": f"Home Assistant Core {HAVERSION}",
                "password": None,
            },
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {
                        "agent_ids": ["test-agent"],
                        "include_addons": ["my-addon"],
                        "include_all_addons": True,
                        "include_database": False,
                        "include_folders": ["share"],
                        "name": "cool_backup",
                        "password": "hunter2",
                    },
                },
            ],
            None,
            {
                "agent_ids": ["test-agent"],
                "include_addons": ["my-addon"],
                "include_all_addons": True,
                "include_database": False,
                "include_folders": ["share"],
                "include_homeassistant": True,
                "name": "cool_backup",
                "password": "hunter2",
                "with_automatic_settings": True,
            },
        ),
    ],
)
async def test_update_core_with_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    commands: list[dict[str, Any]],
    default_mount: str | None,
    expected_kwargs: dict[str, Any],
) -> None:
    """Test updating core update entity."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await setup_backup_integration(hass)

    client = await hass_ws_client(hass)
    for command in commands:
        await client.send_json_auto_id(command)
        result = await client.receive_json()
        assert result["success"]

    supervisor_client.homeassistant.update.return_value = None
    supervisor_client.mounts.info.return_value.default_backup_mount = default_mount
    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
    ) as mock_create_backup:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_core_update", "backup": True},
            blocking=True,
        )
    mock_create_backup.assert_called_once_with(**expected_kwargs)
    supervisor_client.homeassistant.update.assert_called_once_with(
        HomeAssistantUpdateOptions(version=None, backup=False)
    )


async def test_update_supervisor(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """Test updating supervisor update entity."""
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

    supervisor_client.supervisor.update.return_value = None
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.home_assistant_supervisor_update"},
        blocking=True,
    )
    supervisor_client.supervisor.update.assert_called_once()


async def test_update_addon_with_error(
    hass: HomeAssistant,
    update_addon: AsyncMock,
) -> None:
    """Test updating addon update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
    await hass.async_block_till_done()

    update_addon.side_effect = SupervisorError
    with pytest.raises(HomeAssistantError, match=r"^Error updating test:"):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.test_update"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("create_backup_error", "delete_filtered_backups_error", "message"),
    [
        (BackupManagerError, None, r"^Error creating backup: "),
        (None, BackupManagerError, r"^Error deleting old backups: "),
    ],
)
async def test_update_addon_with_backup_and_error(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    create_backup_error: Exception | None,
    delete_filtered_backups_error: Exception | None,
    message: str,
) -> None:
    """Test updating addon update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await setup_backup_integration(hass)

    supervisor_client.homeassistant.update.return_value = None
    supervisor_client.mounts.info.return_value.default_backup_mount = None
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_create_backup",
            side_effect=create_backup_error,
        ),
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_delete_filtered_backups",
            side_effect=delete_filtered_backups_error,
        ),
        pytest.raises(HomeAssistantError, match=message),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.test_update", "backup": True},
            blocking=True,
        )


async def test_update_os_with_error(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """Test updating OS update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
    await hass.async_block_till_done()

    supervisor_client.os.update.side_effect = SupervisorError
    with pytest.raises(
        HomeAssistantError, match=r"^Error updating Home Assistant Operating System:"
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_operating_system_update"},
            blocking=True,
        )


async def test_update_os_with_backup_and_error(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
) -> None:
    """Test updating OS update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await setup_backup_integration(hass)

    supervisor_client.os.update.return_value = None
    supervisor_client.mounts.info.return_value.default_backup_mount = None
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_create_backup",
            side_effect=BackupManagerError,
        ),
        pytest.raises(HomeAssistantError, match=r"^Error creating backup:"),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {
                "entity_id": "update.home_assistant_operating_system_update",
                "backup": True,
            },
            blocking=True,
        )


async def test_update_supervisor_with_error(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """Test updating supervisor update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
    await hass.async_block_till_done()

    supervisor_client.supervisor.update.side_effect = SupervisorError
    with pytest.raises(
        HomeAssistantError, match=r"^Error updating Home Assistant Supervisor:"
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_supervisor_update"},
            blocking=True,
        )


async def test_update_core_with_error(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """Test updating core update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
    await hass.async_block_till_done()

    supervisor_client.homeassistant.update.side_effect = SupervisorError
    with pytest.raises(
        HomeAssistantError, match=r"^Error updating Home Assistant Core:"
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_core_update"},
            blocking=True,
        )


async def test_update_core_with_backup_and_error(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
) -> None:
    """Test updating core update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await setup_backup_integration(hass)

    supervisor_client.homeassistant.update.return_value = None
    supervisor_client.mounts.info.return_value.default_backup_mount = None
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_create_backup",
            side_effect=BackupManagerError,
        ),
        pytest.raises(HomeAssistantError, match=r"^Error creating backup:"),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_core_update", "backup": True},
            blocking=True,
        )


async def test_release_notes_between_versions(
    hass: HomeAssistant,
    addon_changelog: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test release notes between versions."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    addon_changelog.return_value = "# 2.0.1\nNew updates\n# 2.0.0\nOld updates"

    with (
        patch.dict(os.environ, MOCK_ENVIRON),
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.test_update",
        }
    )
    result = await client.receive_json()
    assert "Old updates" not in result["result"]
    assert "New updates" in result["result"]


async def test_release_notes_full(
    hass: HomeAssistant,
    addon_changelog: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test release notes no match."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    full_changelog = "# 2.0.0\nNew updates\n# 2.0.0\nOld updates"
    addon_changelog.return_value = full_changelog

    with (
        patch.dict(os.environ, MOCK_ENVIRON),
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.test_update",
        }
    )
    result = await client.receive_json()
    assert "Old updates" in result["result"]
    assert "New updates" in result["result"]

    # Update entity without update should returns full changelog
    await client.send_json(
        {
            "id": 2,
            "type": "update/release_notes",
            "entity_id": "update.test2_update",
        }
    )
    result = await client.receive_json()
    assert result["result"] == full_changelog


async def test_not_release_notes(
    hass: HomeAssistant,
    addon_changelog: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test handling where there are no release notes."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    addon_changelog.side_effect = SupervisorNotFoundError()

    with (
        patch.dict(os.environ, MOCK_ENVIRON),
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.test_update",
        }
    )
    result = await client.receive_json()
    assert result["result"] is None


async def test_no_os_entity(hass: HomeAssistant) -> None:
    """Test handling where there is no os entity."""
    with (
        patch.dict(os.environ, MOCK_ENVIRON),
        patch(
            "homeassistant.components.hassio.HassIO.get_info",
            return_value={
                "supervisor": "222",
                "homeassistant": "0.110.0",
                "hassos": None,
            },
        ),
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    # Verify that the entity does not exist
    assert not hass.states.get("update.home_assistant_operating_system_update")


async def test_setting_up_core_update_when_addon_fails(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    addon_installed: AsyncMock,
    addon_stats: AsyncMock,
    addon_changelog: AsyncMock,
) -> None:
    """Test setting up core update when single addon fails."""
    addon_installed.side_effect = SupervisorBadRequestError("Addon Test does not exist")
    addon_stats.side_effect = SupervisorBadRequestError("add-on is not running")
    addon_changelog.side_effect = SupervisorBadRequestError("add-on is not running")
    with (
        patch.dict(os.environ, MOCK_ENVIRON),
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        await hass.async_block_till_done()
    assert result

    # There is a REQUEST_REFRESH_DELAYs cooldown on the debouncer
    async_fire_time_changed(
        hass, dt_util.now() + timedelta(seconds=REQUEST_REFRESH_DELAY)
    )
    await hass.async_block_till_done()

    # Verify that the core update entity does exist
    state = hass.states.get("update.home_assistant_core_update")
    assert state
    assert state.state == "on"
