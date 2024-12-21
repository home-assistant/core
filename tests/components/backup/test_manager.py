"""Tests for the Backup integration."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from io import StringIO
import json
from pathlib import Path
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call, mock_open, patch

import pytest

from homeassistant.components.backup import (
    DOMAIN,
    AgentBackup,
    BackupAgentPlatformProtocol,
    BackupManager,
    BackupPlatformProtocol,
    Folder,
    LocalBackupAgent,
    backup as local_backup_platform,
)
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.backup.manager import (
    BackupManagerState,
    CoreBackupReaderWriter,
    CreateBackupEvent,
    CreateBackupStage,
    CreateBackupState,
    NewBackup,
    WrittenBackup,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
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


@pytest.fixture(autouse=True)
def mock_delay_save() -> Generator[None]:
    """Mock the delay save constant."""
    with patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0):
        yield


@pytest.fixture(name="generate_backup_id")
def generate_backup_id_fixture() -> Generator[MagicMock]:
    """Mock generate backup id."""
    with patch("homeassistant.components.backup.manager._generate_backup_id") as mock:
        mock.return_value = "abc123"
        yield mock


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
        backup_name="Custom 2025.1.0",
        extra_metadata={
            "instance_id": hass.data["core.uuid"],
            "with_automatic_settings": False,
        },
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
    ("agent_ids", "backup_directory", "temp_file_unlink_call_count"),
    [
        ([LOCAL_AGENT_ID], "backups", 0),
        (["test.remote"], "tmp_backups", 1),
        ([LOCAL_AGENT_ID, "test.remote"], "backups", 0),
    ],
)
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"include_database": True, "name": "abc123"},
        {"include_database": False},
        {"password": "pass123"},
    ],
)
async def test_async_initiate_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
    generate_backup_id: MagicMock,
    path_glob: MagicMock,
    params: dict[str, Any],
    agent_ids: list[str],
    backup_directory: str,
    temp_file_unlink_call_count: int,
) -> None:
    """Test generate backup."""
    local_agent = local_backup_platform.CoreLocalBackupAgent(hass)
    remote_agent = BackupAgentTest("remote", backups=[])
    agents = {
        f"backup.{local_agent.name}": local_agent,
        f"test.{remote_agent.name}": remote_agent,
    }
    with patch(
        "homeassistant.components.backup.backup.async_get_backup_agents"
    ) as core_get_backup_agents:
        core_get_backup_agents.return_value = [local_agent]
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        await _setup_backup_platform(
            hass,
            domain="test",
            platform=Mock(
                async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
                spec_set=BackupAgentPlatformProtocol,
            ),
        )

    ws_client = await hass_ws_client(hass)

    include_database = params.get("include_database", True)
    name = params.get("name", "Custom 2025.1.0")
    password = params.get("password")
    path_glob.return_value = []

    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()

    assert result["success"] is True
    assert result["result"] == {
        "backups": [],
        "agent_errors": {},
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    with (
        patch("pathlib.Path.open", mock_open(read_data=b"test")),
        patch("pathlib.Path.unlink") as unlink_mock,
    ):
        await ws_client.send_json_auto_id(
            {"type": "backup/generate", "agent_ids": agent_ids} | params
        )
        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.CREATE_BACKUP,
            "stage": None,
            "state": CreateBackupState.IN_PROGRESS,
        }
        result = await ws_client.receive_json()
        assert result["success"] is True

        backup_id = result["result"]["backup_job_id"]
        assert backup_id == generate_backup_id.return_value

        await hass.async_block_till_done()

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "stage": CreateBackupStage.HOME_ASSISTANT,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "stage": CreateBackupStage.UPLOAD_TO_AGENTS,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "stage": None,
        "state": CreateBackupState.COMPLETED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    assert unlink_mock.call_count == temp_file_unlink_call_count

    assert mocked_json_bytes.call_count == 1
    backup_json_dict = mocked_json_bytes.call_args[0][0]
    assert isinstance(backup_json_dict, dict)
    assert backup_json_dict == {
        "compressed": True,
        "date": ANY,
        "extra": {
            "instance_id": hass.data["core.uuid"],
            "with_automatic_settings": False,
        },
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

    await ws_client.send_json_auto_id(
        {"type": "backup/details", "backup_id": backup_id}
    )
    result = await ws_client.receive_json()

    backup_data = result["result"]["backup"]
    backup_agent_ids = backup_data.pop("agent_ids")

    assert backup_agent_ids == agent_ids
    assert backup_data == {
        "addons": [],
        "backup_id": ANY,
        "database_included": include_database,
        "date": ANY,
        "failed_agent_ids": [],
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2025.1.0",
        "name": name,
        "protected": bool(password),
        "size": ANY,
        "with_automatic_settings": False,
    }

    for agent_id in agent_ids:
        agent = agents[agent_id]
        assert len(agent._backups) == 1
        agent_backup = agent._backups[backup_data["backup_id"]]
        assert agent_backup.backup_id == backup_data["backup_id"]
        assert agent_backup.date == backup_data["date"]
        assert agent_backup.name == backup_data["name"]
        assert agent_backup.protected == backup_data["protected"]
        assert agent_backup.size == backup_data["size"]

    outer_tar = mocked_tarfile.return_value
    core_tar = outer_tar.create_inner_tar.return_value.__enter__.return_value
    expected_files = [call(hass.config.path(), arcname="data", recursive=False)] + [
        call(file, arcname=f"data/{file}", recursive=False)
        for file in _EXPECTED_FILES_WITH_DATABASE[include_database]
    ]
    assert core_tar.add.call_args_list == expected_files

    tar_file_path = str(mocked_tarfile.call_args_list[0][0][0])
    backup_directory = hass.config.path(backup_directory)
    assert tar_file_path == f"{backup_directory}/{backup_data["backup_id"]}.tar"


@pytest.mark.usefixtures("mock_backup_generation")
async def test_async_initiate_backup_with_agent_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
    generate_backup_id: MagicMock,
    path_glob: MagicMock,
    hass_storage: dict[str, Any],
) -> None:
    """Test generate backup."""
    agent_ids = [LOCAL_AGENT_ID, "test.remote"]
    local_agent = local_backup_platform.CoreLocalBackupAgent(hass)
    remote_agent = BackupAgentTest("remote", backups=[])

    with patch(
        "homeassistant.components.backup.backup.async_get_backup_agents"
    ) as core_get_backup_agents:
        core_get_backup_agents.return_value = [local_agent]
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        await _setup_backup_platform(
            hass,
            domain="test",
            platform=Mock(
                async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
                spec_set=BackupAgentPlatformProtocol,
            ),
        )

    ws_client = await hass_ws_client(hass)

    path_glob.return_value = []

    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()

    assert result["success"] is True
    assert result["result"] == {
        "backups": [],
        "agent_errors": {},
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    with (
        patch("pathlib.Path.open", mock_open(read_data=b"test")),
        patch.object(
            remote_agent, "async_upload_backup", side_effect=Exception("Test exception")
        ),
    ):
        await ws_client.send_json_auto_id(
            {"type": "backup/generate", "agent_ids": agent_ids}
        )
        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.CREATE_BACKUP,
            "stage": None,
            "state": CreateBackupState.IN_PROGRESS,
        }
        result = await ws_client.receive_json()
        assert result["success"] is True

        backup_id = result["result"]["backup_job_id"]
        assert backup_id == generate_backup_id.return_value

        await hass.async_block_till_done()

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "stage": CreateBackupStage.HOME_ASSISTANT,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "stage": CreateBackupStage.UPLOAD_TO_AGENTS,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "stage": None,
        "state": CreateBackupState.COMPLETED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    expected_backup_data = {
        "addons": [],
        "agent_ids": ["backup.local"],
        "backup_id": "abc123",
        "database_included": True,
        "date": ANY,
        "failed_agent_ids": ["test.remote"],
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2025.1.0",
        "name": "Custom 2025.1.0",
        "protected": False,
        "size": 123,
        "with_automatic_settings": False,
    }

    await ws_client.send_json_auto_id(
        {"type": "backup/details", "backup_id": backup_id}
    )
    result = await ws_client.receive_json()
    assert result["result"] == {
        "agent_errors": {},
        "backup": expected_backup_data,
    }

    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()
    assert result["result"] == {
        "agent_errors": {},
        "backups": [expected_backup_data],
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
    }

    await hass.async_block_till_done()
    assert hass_storage[DOMAIN]["data"]["backups"] == [
        {
            "backup_id": "abc123",
            "failed_agent_ids": ["test.remote"],
        }
    ]


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    ("create_backup_command", "issues_after_create_backup"),
    [
        (
            {"type": "backup/generate", "agent_ids": [LOCAL_AGENT_ID]},
            {(DOMAIN, "automatic_backup_failed")},
        ),
        (
            {"type": "backup/generate_with_automatic_settings"},
            set(),
        ),
    ],
)
async def test_create_backup_success_clears_issue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    create_backup_command: dict[str, Any],
    issues_after_create_backup: set[tuple[str, str]],
) -> None:
    """Test backup issue is cleared after backup is created."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Create a backup issue
    ir.async_create_issue(
        hass,
        DOMAIN,
        "automatic_backup_failed",
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="automatic_backup_failed_create",
    )

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": [LOCAL_AGENT_ID]},
        }
    )
    result = await ws_client.receive_json()
    assert result["success"] is True

    await ws_client.send_json_auto_id(create_backup_command)
    result = await ws_client.receive_json()
    assert result["success"] is True

    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert set(issue_registry.issues) == issues_after_create_backup


async def delayed_boom(*args, **kwargs) -> None:
    """Raise an exception after a delay."""

    async def delayed_boom() -> None:
        await asyncio.sleep(0)
        raise Exception("Boom!")  # noqa: TRY002

    return (NewBackup(backup_job_id="abc123"), delayed_boom())


@pytest.mark.parametrize(
    (
        "create_backup_command",
        "create_backup_side_effect",
        "agent_upload_side_effect",
        "create_backup_result",
        "issues_after_create_backup",
    ),
    [
        # No error
        (
            {"type": "backup/generate", "agent_ids": ["test.remote"]},
            None,
            None,
            True,
            {},
        ),
        (
            {"type": "backup/generate_with_automatic_settings"},
            None,
            None,
            True,
            {},
        ),
        # Error raised in async_initiate_backup
        (
            {"type": "backup/generate", "agent_ids": ["test.remote"]},
            Exception("Boom!"),
            None,
            False,
            {},
        ),
        (
            {"type": "backup/generate_with_automatic_settings"},
            Exception("Boom!"),
            None,
            False,
            {
                (DOMAIN, "automatic_backup_failed"): {
                    "translation_key": "automatic_backup_failed_create",
                    "translation_placeholders": None,
                }
            },
        ),
        # Error raised when awaiting the backup task
        (
            {"type": "backup/generate", "agent_ids": ["test.remote"]},
            delayed_boom,
            None,
            True,
            {},
        ),
        (
            {"type": "backup/generate_with_automatic_settings"},
            delayed_boom,
            None,
            True,
            {
                (DOMAIN, "automatic_backup_failed"): {
                    "translation_key": "automatic_backup_failed_create",
                    "translation_placeholders": None,
                }
            },
        ),
        # Error raised in async_upload_backup
        (
            {"type": "backup/generate", "agent_ids": ["test.remote"]},
            None,
            Exception("Boom!"),
            True,
            {},
        ),
        (
            {"type": "backup/generate_with_automatic_settings"},
            None,
            Exception("Boom!"),
            True,
            {
                (DOMAIN, "automatic_backup_failed"): {
                    "translation_key": "automatic_backup_failed_upload_agents",
                    "translation_placeholders": {"failed_agents": "test.remote"},
                }
            },
        ),
    ],
)
async def test_create_backup_failure_raises_issue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    create_backup: AsyncMock,
    create_backup_command: dict[str, Any],
    create_backup_side_effect: Exception | None,
    agent_upload_side_effect: Exception | None,
    create_backup_result: bool,
    issues_after_create_backup: dict[tuple[str, str], dict[str, Any]],
) -> None:
    """Test backup issue is cleared after backup is created."""
    remote_agent = BackupAgentTest("remote", backups=[])

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
            spec_set=BackupAgentPlatformProtocol,
        ),
    )

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    create_backup.side_effect = create_backup_side_effect

    await ws_client.send_json_auto_id(
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test.remote"]},
        }
    )
    result = await ws_client.receive_json()
    assert result["success"] is True

    with patch.object(
        remote_agent, "async_upload_backup", side_effect=agent_upload_side_effect
    ):
        await ws_client.send_json_auto_id(create_backup_command)
        result = await ws_client.receive_json()
        assert result["success"] == create_backup_result
        await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert set(issue_registry.issues) == set(issues_after_create_backup)
    for issue_id, issue_data in issues_after_create_backup.items():
        issue = issue_registry.issues[issue_id]
        assert issue.translation_key == issue_data["translation_key"]
        assert issue.translation_placeholders == issue_data["translation_placeholders"]


async def test_loading_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass, CoreBackupReaderWriter(hass))

    assert not manager.platforms

    get_agents_mock = AsyncMock(return_value=[])

    await _setup_backup_platform(
        hass,
        platform=Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
            async_get_backup_agents=get_agents_mock,
        ),
    )
    await manager.load_platforms()
    await hass.async_block_till_done()

    assert len(manager.platforms) == 1
    assert "Loaded 1 platforms" in caplog.text

    get_agents_mock.assert_called_once_with(hass)


class LocalBackupAgentTest(BackupAgentTest, LocalBackupAgent):
    """Local backup agent."""

    def get_backup_path(self, backup_id: str) -> Path:
        """Return the local path to a backup."""
        return "test.tar"


@pytest.mark.parametrize(
    ("agent_class", "num_local_agents"),
    [(LocalBackupAgentTest, 2), (BackupAgentTest, 1)],
)
async def test_loading_platform_with_listener(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    agent_class: type[BackupAgentTest],
    num_local_agents: int,
) -> None:
    """Test loading a backup agent platform which can be listened to."""
    ws_client = await hass_ws_client(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    manager = hass.data[DATA_MANAGER]

    get_agents_mock = AsyncMock(return_value=[agent_class("remote1", backups=[])])
    register_listener_mock = Mock()

    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=get_agents_mock,
            async_register_backup_agents_listener=register_listener_mock,
        ),
    )
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local"},
        {"agent_id": "test.remote1"},
    ]
    assert len(manager.local_backup_agents) == num_local_agents

    get_agents_mock.assert_called_once_with(hass)
    register_listener_mock.assert_called_once_with(hass, listener=ANY)

    get_agents_mock.reset_mock()
    get_agents_mock.return_value = [agent_class("remote2", backups=[])]
    listener = register_listener_mock.call_args[1]["listener"]
    listener()

    get_agents_mock.assert_called_once_with(hass)
    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local"},
        {"agent_id": "test.remote2"},
    ]
    assert len(manager.local_backup_agents) == num_local_agents


@pytest.mark.parametrize(
    "platform_mock",
    [
        Mock(async_pre_backup=AsyncMock(), spec=["async_pre_backup"]),
        Mock(async_post_backup=AsyncMock(), spec=["async_post_backup"]),
        Mock(spec=[]),
    ],
)
async def test_not_loading_bad_platforms(
    hass: HomeAssistant,
    platform_mock: Mock,
) -> None:
    """Test not loading bad backup platforms."""
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=platform_mock,
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert platform_mock.mock_calls == []


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


@pytest.mark.parametrize(
    (
        "agent_id_params",
        "open_call_count",
        "move_call_count",
        "move_path_names",
        "remote_agent_backups",
        "remote_agent_backup_data",
        "temp_file_unlink_call_count",
    ),
    [
        (
            "agent_id=backup.local&agent_id=test.remote",
            2,
            1,
            ["abc123.tar"],
            {TEST_BACKUP_ABC123.backup_id: TEST_BACKUP_ABC123},
            b"test",
            0,
        ),
        (
            "agent_id=backup.local",
            1,
            1,
            ["abc123.tar"],
            {},
            None,
            0,
        ),
        (
            "agent_id=test.remote",
            2,
            0,
            [],
            {TEST_BACKUP_ABC123.backup_id: TEST_BACKUP_ABC123},
            b"test",
            1,
        ),
    ],
)
async def test_receive_backup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    agent_id_params: str,
    open_call_count: int,
    move_call_count: int,
    move_path_names: list[str],
    remote_agent_backups: dict[str, AgentBackup],
    remote_agent_backup_data: bytes | None,
    temp_file_unlink_call_count: int,
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
        patch("pathlib.Path.unlink") as unlink_mock,
    ):
        resp = await client.post(
            f"/api/backup/upload?{agent_id_params}",
            data={"file": StringIO(upload_data)},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    assert open_mock.call_count == open_call_count
    assert move_mock.call_count == move_call_count
    for index, name in enumerate(move_path_names):
        assert move_mock.call_args_list[index].args[1].name == name
    assert remote_agent._backups == remote_agent_backups
    assert remote_agent._backup_data == remote_agent_backup_data
    assert unlink_mock.call_count == temp_file_unlink_call_count


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
        patch(
            "homeassistant.components.backup.manager.validate_password"
        ) as validate_password_mock,
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
        backup_path = f"{hass.config.path()}/{dir}/abc123.tar"
        expected_restore_file = json.dumps(
            {
                "path": backup_path,
                "password": password,
                "remove_after_restore": agent_id != LOCAL_AGENT_ID,
                "restore_database": restore_database,
                "restore_homeassistant": restore_homeassistant,
            }
        )
        validate_password_mock.assert_called_once_with(Path(backup_path), password)
        assert mocked_write_text.call_args[0][0] == expected_restore_file
        assert mocked_service_call.called


async def test_async_trigger_restore_wrong_password(hass: HomeAssistant) -> None:
    """Test trigger restore."""
    password = "hunter2"
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
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
        patch(
            "homeassistant.components.backup.manager.validate_password"
        ) as validate_password_mock,
    ):
        validate_password_mock.return_value = False
        with pytest.raises(
            HomeAssistantError, match="The password provided is incorrect."
        ):
            await manager.async_restore_backup(
                TEST_BACKUP_ABC123.backup_id,
                agent_id=LOCAL_AGENT_ID,
                password=password,
                restore_addons=None,
                restore_database=True,
                restore_folders=None,
                restore_homeassistant=True,
            )

        backup_path = f"{hass.config.path()}/backups/abc123.tar"
        validate_password_mock.assert_called_once_with(Path(backup_path), password)
        mocked_write_text.assert_not_called()
        mocked_service_call.assert_not_called()


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
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
        pytest.raises(HomeAssistantError, match=expected_error),
    ):
        await manager.async_restore_backup(**(default_parameters | parameters))

    mocked_write_text.assert_not_called()
    mocked_service_call.assert_not_called()
