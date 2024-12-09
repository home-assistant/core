"""Tests for the Backup integration."""

from __future__ import annotations

import asyncio
from io import StringIO
import json
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock, call, mock_open, patch

import pytest

from homeassistant.components.backup import (
    DOMAIN,
    AgentBackup,
    BackupAgentPlatformProtocol,
    BackupManager,
    BackupPlatformProtocol,
    Folder,
    backup as local_backup_platform,
)
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.backup.manager import (
    CoreBackupReaderWriter,
    CreateBackupEvent,
    CreateBackupStage,
    CreateBackupState,
    IdleEvent,
    ManagerStateEvent,
    NewBackup,
    WrittenBackup,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import (
    LOCAL_AGENT_ID,
    TEST_BACKUP_ABC123,
    TEST_BACKUP_DEF456,
    BackupAgentTest,
)

from tests.common import MockPlatform, mock_platform
from tests.typing import ClientSessionGenerator, WebSocketGenerator

_EXPECTED_FILES = [
    "test.txt",
    ".storage",
    "backups",
    "backups/not_backup",
    "tmp_backups",
    "tmp_backups/not_backup",
]
_EXPECTED_FILES_WITH_DATABASE = {
    True: [*_EXPECTED_FILES, "home-assistant_v2.db"],
    False: _EXPECTED_FILES,
}


async def _mock_backup_generation(
    hass: HomeAssistant,
    manager: BackupManager,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
    *,
    agent_ids: list[str] | None = None,
    include_database: bool = True,
    name: str | None = "Core 2025.1.0",
    password: str | None = None,
) -> AgentBackup:
    """Mock backup generator."""

    agent_ids = agent_ids or [LOCAL_AGENT_ID]
    progress: list[ManagerStateEvent] = []

    def on_progress(_progress: ManagerStateEvent) -> None:
        """Mock progress callback."""
        progress.append(_progress)

    assert manager._backup_task is None
    manager.async_subscribe_events(on_progress)
    await manager.async_initiate_backup(
        agent_ids=agent_ids,
        include_addons=[],
        include_all_addons=False,
        include_database=include_database,
        include_folders=[],
        include_homeassistant=True,
        name=name,
        password=password,
    )
    assert manager._backup_task is not None
    assert progress == [
        CreateBackupEvent(stage=None, state=CreateBackupState.IN_PROGRESS)
    ]

    finished_backup = await manager._backup_task
    await manager._backup_finish_task
    assert progress == [
        CreateBackupEvent(stage=None, state=CreateBackupState.IN_PROGRESS),
        CreateBackupEvent(
            stage=CreateBackupStage.HOME_ASSISTANT, state=CreateBackupState.IN_PROGRESS
        ),
        CreateBackupEvent(
            stage=CreateBackupStage.UPLOAD_TO_AGENTS,
            state=CreateBackupState.IN_PROGRESS,
        ),
        CreateBackupEvent(stage=None, state=CreateBackupState.COMPLETED),
        IdleEvent(),
    ]

    assert mocked_json_bytes.call_count == 1
    backup_json_dict = mocked_json_bytes.call_args[0][0]
    assert isinstance(backup_json_dict, dict)
    assert backup_json_dict == {
        "compressed": True,
        "date": ANY,
        "homeassistant": {
            "exclude_database": not include_database,
            "version": "2025.1.0",
        },
        "name": name,
        "protected": bool(password),
        "slug": ANY,
        "type": "partial",
        "version": 2,
    }
    backup = finished_backup.backup
    assert isinstance(backup, AgentBackup)
    assert backup == AgentBackup(
        addons=[],
        backup_id=ANY,
        database_included=include_database,
        date=ANY,
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2025.1.0",
        name=name,
        protected=bool(password),
        size=ANY,
    )
    for agent_id in agent_ids:
        agent = manager.backup_agents[agent_id]
        assert len(agent._backups) == 1
        agent_backup = agent._backups[backup.backup_id]
        assert agent_backup.backup_id == backup.backup_id
        assert agent_backup.date == backup.date
        assert agent_backup.name == backup.name
        assert agent_backup.protected == backup.protected
        assert agent_backup.size == backup.size

    outer_tar = mocked_tarfile.return_value
    core_tar = outer_tar.create_inner_tar.return_value.__enter__.return_value
    expected_files = [call(hass.config.path(), arcname="data", recursive=False)] + [
        call(file, arcname=f"data/{file}", recursive=False)
        for file in _EXPECTED_FILES_WITH_DATABASE[include_database]
    ]
    assert core_tar.add.call_args_list == expected_files

    return backup


async def _setup_backup_platform(
    hass: HomeAssistant,
    *,
    domain: str = "some_domain",
    platform: BackupPlatformProtocol | BackupAgentPlatformProtocol | None = None,
) -> None:
    """Set up a mock domain."""
    mock_platform(hass, f"{domain}.backup", platform or MockPlatform())
    assert await async_setup_component(hass, domain, {})
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_backup_generation")
async def test_async_create_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
) -> None:
    """Test create backup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    new_backup = NewBackup(backup_job_id="time-123")
    backup_task = AsyncMock(
        return_value=WrittenBackup(
            backup=TEST_BACKUP_ABC123,
            open_stream=AsyncMock(),
            release_stream=AsyncMock(),
        ),
    )()  # call it so that it can be awaited

    with patch(
        "homeassistant.components.backup.manager.CoreBackupReaderWriter.async_create_backup",
        return_value=(new_backup, backup_task),
    ) as create_backup:
        await hass.services.async_call(
            DOMAIN,
            "create",
            blocking=True,
        )

    assert create_backup.called
    assert create_backup.call_args == call(
        agent_ids=["backup.local"],
        backup_name="Core 2025.1.0",
        include_addons=None,
        include_all_addons=False,
        include_database=True,
        include_folders=None,
        include_homeassistant=True,
        on_progress=ANY,
        password=None,
    )


async def test_async_create_backup_when_backing_up(hass: HomeAssistant) -> None:
    """Test generate backup."""
    manager = BackupManager(hass, CoreBackupReaderWriter(hass))
    manager.last_event = CreateBackupEvent(
        stage=None, state=CreateBackupState.IN_PROGRESS
    )
    with pytest.raises(HomeAssistantError, match="Backup manager busy"):
        await manager.async_create_backup(
            agent_ids=[LOCAL_AGENT_ID],
            include_addons=[],
            include_all_addons=False,
            include_database=True,
            include_folders=[],
            include_homeassistant=True,
            name=None,
            password=None,
        )


@pytest.mark.parametrize(
    ("parameters", "expected_error"),
    [
        ({"agent_ids": []}, "At least one agent must be selected"),
        ({"agent_ids": ["non_existing"]}, "Invalid agent selected"),
        (
            {"include_addons": ["ssl"], "include_all_addons": True},
            "Cannot include all addons and specify specific addons",
        ),
        ({"include_homeassistant": False}, "Home Assistant must be included in backup"),
    ],
)
async def test_create_backup_wrong_parameters(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    parameters: dict[str, Any],
    expected_error: str,
) -> None:
    """Test create backup with wrong parameters."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    default_parameters = {
        "agent_ids": [LOCAL_AGENT_ID],
        "include_addons": [],
        "include_all_addons": False,
        "include_database": True,
        "include_folders": [],
        "include_homeassistant": True,
    }

    await ws_client.send_json_auto_id(
        {"type": "backup/generate"} | default_parameters | parameters
    )
    result = await ws_client.receive_json()

    assert result["success"] is False
    assert result["error"]["code"] == "home_assistant_error"
    assert result["error"]["message"] == expected_error


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    ("agent_ids", "backup_directory"),
    [
        ([LOCAL_AGENT_ID], "backups"),
        (["test.remote"], "tmp_backups"),
        ([LOCAL_AGENT_ID, "test.remote"], "backups"),
    ],
)
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"include_database": True, "name": "abc123"},
        {"include_database": False},
        {"password": "abc123"},
    ],
)
async def test_async_initiate_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
    params: dict,
    agent_ids: list[str],
    backup_directory: str,
) -> None:
    """Test generate backup."""
    manager = BackupManager(hass, CoreBackupReaderWriter(hass))
    hass.data[DATA_MANAGER] = manager

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=AsyncMock(
                return_value=[BackupAgentTest("remote", backups=[])]
            ),
            spec_set=BackupAgentPlatformProtocol,
        ),
    )
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._loaded_backups = True

    backup = await _mock_backup_generation(
        hass, manager, mocked_json_bytes, mocked_tarfile, agent_ids=agent_ids, **params
    )

    assert "Generated new backup with backup_id " in caplog.text
    assert "Loaded 0 platforms" in caplog.text
    assert "Loaded 2 agents" in caplog.text

    tar_file_path = str(mocked_tarfile.call_args_list[0][0][0])
    backup_directory = hass.config.path(backup_directory)
    assert tar_file_path == f"{backup_directory}/{backup.backup_id}.tar"
    assert isinstance(tar_file_path, str)


async def test_loading_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass, CoreBackupReaderWriter(hass))

    assert not manager.platforms

    await _setup_backup_platform(
        hass,
        platform=Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(),
        ),
    )
    await manager.load_platforms()
    await hass.async_block_till_done()

    assert len(manager.platforms) == 1

    assert "Loaded 1 platforms" in caplog.text


async def test_not_loading_bad_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass, CoreBackupReaderWriter(hass))

    assert not manager.platforms

    await _setup_backup_platform(hass)
    await manager.load_platforms()
    await hass.async_block_till_done()

    assert len(manager.platforms) == 0

    assert "Loaded 0 platforms" in caplog.text


async def test_exception_platform_pre(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test exception in pre step."""

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    remote_agent = BackupAgentTest("remote", backups=[])
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_pre_backup=_mock_step,
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
        ),
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "create",
        blocking=True,
    )

    assert "Generating backup failed" in caplog.text
    assert "Test exception" in caplog.text


@pytest.mark.usefixtures("mock_backup_generation")
async def test_exception_platform_post(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception in post step."""

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    remote_agent = BackupAgentTest("remote", backups=[])
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=_mock_step,
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
        ),
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "create",
        blocking=True,
    )

    assert "Generating backup failed" in caplog.text
    assert "Test exception" in caplog.text


async def test_receive_backup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test receive backup and upload to the local and a remote agent."""
    remote_agent = BackupAgentTest("remote", backups=[])
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
            spec_set=BackupAgentPlatformProtocol,
        ),
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_client()

    upload_data = "test"
    open_mock = mock_open(read_data=upload_data.encode(encoding="utf-8"))

    with (
        patch("pathlib.Path.open", open_mock),
        patch("shutil.move") as move_mock,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_BACKUP_ABC123,
        ),
    ):
        resp = await client.post(
            "/api/backup/upload?agent_id=backup.local&agent_id=test.remote",
            data={"file": StringIO(upload_data)},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    assert open_mock.call_count == 2
    assert move_mock.call_count == 1
    assert move_mock.mock_calls[0].args[1].name == "abc123.tar"
    assert remote_agent._backups == {TEST_BACKUP_ABC123.backup_id: TEST_BACKUP_ABC123}
    assert remote_agent._backup_data == upload_data.encode(encoding="utf-8")


@pytest.mark.usefixtures("mock_backup_generation")
async def test_receive_backup_busy_manager(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test receive backup with a busy manager."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_client()
    ws_client = await hass_ws_client(hass)

    upload_data = "test"

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})
    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": "idle"}

    result = await ws_client.receive_json()
    assert result["success"] is True

    new_backup = NewBackup(backup_job_id="time-123")
    backup_task: asyncio.Future[WrittenBackup] = asyncio.Future()
    with patch(
        "homeassistant.components.backup.manager.CoreBackupReaderWriter.async_create_backup",
        return_value=(new_backup, backup_task),
    ) as create_backup:
        await ws_client.send_json_auto_id(
            {"type": "backup/generate", "agent_ids": ["backup.local"]}
        )
        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": "create_backup",
            "stage": None,
            "state": "in_progress",
        }
        result = await ws_client.receive_json()
        assert result["success"] is True
        assert result["result"] == {"backup_job_id": "time-123"}

    assert create_backup.call_count == 1

    resp = await client.post(
        "/api/backup/upload?agent_id=backup.local",
        data={"file": StringIO(upload_data)},
    )

    assert resp.status == 500
    assert (
        await resp.text()
        == "Can't upload backup file: Backup manager busy: create_backup"
    )

    # finish the backup
    backup_task.set_result(
        WrittenBackup(
            backup=TEST_BACKUP_ABC123,
            open_stream=AsyncMock(),
            release_stream=AsyncMock(),
        )
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("agent_id", "password", "restore_database", "restore_homeassistant", "dir"),
    [
        (LOCAL_AGENT_ID, None, True, False, "backups"),
        (LOCAL_AGENT_ID, "abc123", False, True, "backups"),
        ("test.remote", None, True, True, "tmp_backups"),
    ],
)
async def test_async_trigger_restore(
    hass: HomeAssistant,
    agent_id: str,
    password: str | None,
    restore_database: bool,
    restore_homeassistant: bool,
    dir: str,
) -> None:
    """Test trigger restore."""
    manager = BackupManager(hass, CoreBackupReaderWriter(hass))
    hass.data[DATA_MANAGER] = manager

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=AsyncMock(
                return_value=[BackupAgentTest("remote", backups=[TEST_BACKUP_ABC123])]
            ),
            spec_set=BackupAgentPlatformProtocol,
        ),
    )
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._backups = {TEST_BACKUP_ABC123.backup_id: TEST_BACKUP_ABC123}
    local_agent._loaded_backups = True

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open"),
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
        patch.object(BackupAgentTest, "async_download_backup") as download_mock,
    ):
        download_mock.return_value.__aiter__.return_value = iter((b"backup data",))
        await manager.async_restore_backup(
            TEST_BACKUP_ABC123.backup_id,
            agent_id=agent_id,
            password=password,
            restore_addons=None,
            restore_database=restore_database,
            restore_folders=None,
            restore_homeassistant=restore_homeassistant,
        )
        expected_restore_file = json.dumps(
            {
                "path": f"{hass.config.path()}/{dir}/abc123.tar",
                "password": password,
                "remove_after_restore": agent_id != LOCAL_AGENT_ID,
                "restore_database": restore_database,
                "restore_homeassistant": restore_homeassistant,
            }
        )
        assert mocked_write_text.call_args[0][0] == expected_restore_file
        assert mocked_service_call.called


@pytest.mark.parametrize(
    ("parameters", "expected_error"),
    [
        (
            {"backup_id": TEST_BACKUP_DEF456.backup_id},
            "Backup def456 not found",
        ),
        (
            {"restore_addons": ["blah"]},
            "Addons and folders are not supported in core restore",
        ),
        (
            {"restore_folders": [Folder.ADDONS]},
            "Addons and folders are not supported in core restore",
        ),
        (
            {"restore_database": False, "restore_homeassistant": False},
            "Home Assistant or database must be included in restore",
        ),
    ],
)
async def test_async_trigger_restore_wrong_parameters(
    hass: HomeAssistant, parameters: dict[str, Any], expected_error: str
) -> None:
    """Test trigger restore."""
    manager = BackupManager(hass, CoreBackupReaderWriter(hass))

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._backups = {TEST_BACKUP_ABC123.backup_id: TEST_BACKUP_ABC123}
    local_agent._loaded_backups = True

    default_parameters = {
        "agent_id": LOCAL_AGENT_ID,
        "backup_id": TEST_BACKUP_ABC123.backup_id,
        "password": None,
        "restore_addons": None,
        "restore_database": True,
        "restore_folders": None,
        "restore_homeassistant": True,
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        pytest.raises(HomeAssistantError, match=expected_error),
    ):
        await manager.async_restore_backup(**(default_parameters | parameters))
