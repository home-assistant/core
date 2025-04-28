"""Tests for the Backup integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
import re
import tarfile
from typing import Any
from unittest.mock import (
    ANY,
    DEFAULT,
    AsyncMock,
    MagicMock,
    Mock,
    call,
    mock_open,
    patch,
)

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.backup import (
    DOMAIN,
    AgentBackup,
    BackupReaderWriterError,
    Folder,
    LocalBackupAgent,
)
from homeassistant.components.backup.agent import BackupAgentError
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.backup.manager import (
    BackupManagerError,
    BackupManagerExceptionGroup,
    BackupManagerState,
    CreateBackupStage,
    CreateBackupState,
    NewBackup,
    ReceiveBackupStage,
    ReceiveBackupState,
    RestoreBackupState,
    WrittenBackup,
)
from homeassistant.components.backup.util import password_to_key
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .common import (
    LOCAL_AGENT_ID,
    TEST_BACKUP_ABC123,
    TEST_BACKUP_DEF456,
    TEST_BACKUP_PATH_ABC123,
    TEST_BACKUP_PATH_DEF456,
    mock_backup_agent,
    setup_backup_integration,
    setup_backup_platform,
)

from tests.typing import ClientSessionGenerator, WebSocketGenerator

_EXPECTED_FILES = [
    "test.txt",
    ".storage",
    "another_subdir",
    "another_subdir/backups",
    "another_subdir/backups/backup.tar",
    "another_subdir/backups/not_backup",
    "another_subdir/tts",
    "another_subdir/tts/voice.mp3",
    "backups",
    "backups/not_backup",
    "tmp_backups",
    "tmp_backups/not_backup",
    "tts",
]
_EXPECTED_FILES_WITH_DATABASE = {
    True: [*_EXPECTED_FILES, "home-assistant_v2.db"],
    False: _EXPECTED_FILES,
}


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


def mock_read_backup(backup_path: Path) -> AgentBackup:
    """Mock read backup."""
    mock_backups = {
        "abc123": TEST_BACKUP_ABC123,
        "custom_def456": TEST_BACKUP_DEF456,
    }
    return mock_backups[backup_path.stem]


@pytest.mark.usefixtures("mock_backup_generation")
async def test_create_backup_service(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
) -> None:
    """Test create backup service."""
    await setup_backup_integration(hass)

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
        backup_name="Custom backup 2025.1.0",
        extra_metadata={
            "instance_id": "our_uuid",
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


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    ("manager_kwargs", "expected_writer_kwargs"),
    [
        (
            {
                "agent_ids": ["backup.local"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": None,
                "password": None,
            },
            {
                "agent_ids": ["backup.local"],
                "backup_name": "Custom backup 2025.1.0",
                "extra_metadata": {
                    "instance_id": ANY,
                    "with_automatic_settings": False,
                },
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "on_progress": ANY,
                "password": None,
            },
        ),
        (
            {
                "agent_ids": ["backup.local"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": None,
                "password": None,
                "with_automatic_settings": True,
            },
            {
                "agent_ids": ["backup.local"],
                "backup_name": "Automatic backup 2025.1.0",
                "extra_metadata": {
                    "instance_id": ANY,
                    "with_automatic_settings": True,
                },
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "on_progress": ANY,
                "password": None,
            },
        ),
        (
            {
                "agent_ids": ["backup.local"],
                "extra_metadata": {"custom": "data"},
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": None,
                "password": None,
            },
            {
                "agent_ids": ["backup.local"],
                "backup_name": "Custom backup 2025.1.0",
                "extra_metadata": {
                    "custom": "data",
                    "instance_id": ANY,
                    "with_automatic_settings": False,
                },
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "on_progress": ANY,
                "password": None,
            },
        ),
        (
            {
                "agent_ids": ["backup.local"],
                "extra_metadata": {"custom": "data"},
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": "user defined name",
                "password": None,
            },
            {
                "agent_ids": ["backup.local"],
                "backup_name": "user defined name",
                "extra_metadata": {
                    "custom": "data",
                    "instance_id": ANY,
                    "with_automatic_settings": False,
                },
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "on_progress": ANY,
                "password": None,
            },
        ),
        (
            {
                "agent_ids": ["backup.local"],
                "extra_metadata": {"custom": "data"},
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": "  ",  # Name which is just whitespace
                "password": None,
            },
            {
                "agent_ids": ["backup.local"],
                "backup_name": "Custom backup 2025.1.0",
                "extra_metadata": {
                    "custom": "data",
                    "instance_id": ANY,
                    "with_automatic_settings": False,
                },
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "on_progress": ANY,
                "password": None,
            },
        ),
    ],
)
async def test_async_create_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
    manager_kwargs: dict[str, Any],
    expected_writer_kwargs: dict[str, Any],
) -> None:
    """Test create backup."""
    await setup_backup_integration(hass)
    manager = hass.data[DATA_MANAGER]

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
        await manager.async_create_backup(**manager_kwargs)

    assert create_backup.called
    assert create_backup.call_args == call(**expected_writer_kwargs)


@pytest.mark.usefixtures("mock_backup_generation")
async def test_create_backup_when_busy(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test generate backup with busy manager."""
    await setup_backup_integration(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": [LOCAL_AGENT_ID]}
    )
    result = await ws_client.receive_json()

    assert result["success"] is True

    await ws_client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": [LOCAL_AGENT_ID]}
    )
    result = await ws_client.receive_json()

    assert result["success"] is False
    assert result["error"]["code"] == "home_assistant_error"
    assert result["error"]["message"] == "Backup manager busy: create_backup"


@pytest.mark.parametrize(
    ("parameters", "expected_error"),
    [
        (
            {"agent_ids": []},
            "At least one available backup agent must be selected, got []",
        ),
        (
            {"agent_ids": ["non_existing"]},
            "At least one available backup agent must be selected, got ['non_existing']",
        ),
        (
            {"include_addons": ["ssl"], "include_all_addons": True},
            "Cannot include all addons and specify specific addons",
        ),
        (
            {"include_homeassistant": False},
            "Home Assistant must be included in backup",
        ),
    ],
)
async def test_create_backup_wrong_parameters(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    parameters: dict[str, Any],
    expected_error: str,
) -> None:
    """Test create backup with wrong parameters."""
    await setup_backup_integration(hass)

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
    (
        "agent_ids",
        "backup_directory",
        "name",
        "expected_name",
        "expected_filename",
        "expected_agent_ids",
        "expected_failed_agent_ids",
        "temp_file_unlink_call_count",
    ),
    [
        (
            [LOCAL_AGENT_ID],
            "backups",
            None,
            "Custom backup 2025.1.0",
            "Custom_backup_2025.1.0_2025-01-30_05.42_12345678.tar",
            [LOCAL_AGENT_ID],
            [],
            0,
        ),
        (
            ["test.remote"],
            "tmp_backups",
            None,
            "Custom backup 2025.1.0",
            "abc123.tar",  # We don't use friendly name for temporary backups
            ["test.remote"],
            [],
            1,
        ),
        (
            [LOCAL_AGENT_ID, "test.remote"],
            "backups",
            None,
            "Custom backup 2025.1.0",
            "Custom_backup_2025.1.0_2025-01-30_05.42_12345678.tar",
            [LOCAL_AGENT_ID, "test.remote"],
            [],
            0,
        ),
        (
            [LOCAL_AGENT_ID],
            "backups",
            "custom_name",
            "custom_name",
            "custom_name_2025-01-30_05.42_12345678.tar",
            [LOCAL_AGENT_ID],
            [],
            0,
        ),
        (
            ["test.remote"],
            "tmp_backups",
            "custom_name",
            "custom_name",
            "abc123.tar",  # We don't use friendly name for temporary backups
            ["test.remote"],
            [],
            1,
        ),
        (
            [LOCAL_AGENT_ID, "test.remote"],
            "backups",
            "custom_name",
            "custom_name",
            "custom_name_2025-01-30_05.42_12345678.tar",
            [LOCAL_AGENT_ID, "test.remote"],
            [],
            0,
        ),
        (
            # Test we create a backup when at least one agent is available
            [LOCAL_AGENT_ID, "test.unavailable"],
            "backups",
            "custom_name",
            "custom_name",
            "custom_name_2025-01-30_05.42_12345678.tar",
            [LOCAL_AGENT_ID],
            ["test.unavailable"],
            0,
        ),
    ],
)
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"include_database": True},
        {"include_database": False},
        {"password": "pass123"},
    ],
)
async def test_initiate_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
    generate_backup_id: MagicMock,
    path_glob: MagicMock,
    params: dict[str, Any],
    agent_ids: list[str],
    backup_directory: str,
    name: str | None,
    expected_name: str,
    expected_filename: str,
    expected_agent_ids: list[str],
    expected_failed_agent_ids: list[str],
    temp_file_unlink_call_count: int,
) -> None:
    """Test generate backup."""
    await setup_backup_integration(hass, remote_agents=["test.remote"])

    ws_client = await hass_ws_client(hass)
    freezer.move_to("2025-01-30 13:42:12.345678")

    include_database = params.get("include_database", True)
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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
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
            {"type": "backup/generate", "agent_ids": agent_ids, "name": name} | params
        )
        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.CREATE_BACKUP,
            "reason": None,
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
        "reason": None,
        "stage": CreateBackupStage.HOME_ASSISTANT,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
        "stage": CreateBackupStage.UPLOAD_TO_AGENTS,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
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
            "instance_id": "our_uuid",
            "with_automatic_settings": False,
        },
        "homeassistant": {
            "exclude_database": not include_database,
            "version": "2025.1.0",
        },
        "name": expected_name,
        "protected": bool(password),
        "slug": backup_id,
        "type": "partial",
        "version": 2,
    }

    await ws_client.send_json_auto_id(
        {"type": "backup/details", "backup_id": backup_id}
    )
    result = await ws_client.receive_json()

    backup_data = result["result"]["backup"]

    assert backup_data == {
        "addons": [],
        "agents": {
            agent_id: {"protected": bool(password), "size": ANY}
            for agent_id in expected_agent_ids
        },
        "backup_id": backup_id,
        "database_included": include_database,
        "date": ANY,
        "extra_metadata": {"instance_id": "our_uuid", "with_automatic_settings": False},
        "failed_agent_ids": expected_failed_agent_ids,
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2025.1.0",
        "name": expected_name,
        "with_automatic_settings": False,
    }

    outer_tar = mocked_tarfile.return_value
    core_tar = outer_tar.create_inner_tar.return_value.__enter__.return_value
    expected_files = [call(hass.config.path(), arcname="data", recursive=False)] + [
        call(file, arcname=f"data/{file}", recursive=False)
        for file in _EXPECTED_FILES_WITH_DATABASE[include_database]
    ]
    assert core_tar.add.call_args_list == expected_files

    tar_file_path = str(mocked_tarfile.call_args_list[0][0][0])
    backup_directory = hass.config.path(backup_directory)
    assert tar_file_path == f"{backup_directory}/{expected_filename}"


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize("exception", [BackupAgentError("Boom!"), Exception("Boom!")])
async def test_initiate_backup_with_agent_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    generate_backup_id: MagicMock,
    path_glob: MagicMock,
    hass_storage: dict[str, Any],
    exception: Exception,
) -> None:
    """Test agent upload error during backup generation."""
    agent_ids = [LOCAL_AGENT_ID, "test.remote"]
    backup_1 = replace(TEST_BACKUP_ABC123, backup_id="backup1")  # matching instance id
    backup_2 = replace(TEST_BACKUP_DEF456, backup_id="backup2")  # other instance id
    backup_3 = replace(TEST_BACKUP_ABC123, backup_id="backup3")  # matching instance id
    backups_info: list[dict[str, Any]] = [
        {
            "addons": [
                {
                    "name": "Test",
                    "slug": "test",
                    "version": "1.0.0",
                },
            ],
            "agents": {"test.remote": {"protected": False, "size": 0}},
            "backup_id": "backup1",
            "database_included": True,
            "date": "1970-01-01T00:00:00.000Z",
            "extra_metadata": {
                "instance_id": "our_uuid",
                "with_automatic_settings": True,
            },
            "failed_agent_ids": [],
            "folders": [
                "media",
                "share",
            ],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Test",
            "with_automatic_settings": True,
        },
        {
            "addons": [],
            "agents": {"test.remote": {"protected": False, "size": 1}},
            "backup_id": "backup2",
            "database_included": False,
            "date": "1980-01-01T00:00:00.000Z",
            "extra_metadata": {
                "instance_id": "unknown_uuid",
                "with_automatic_settings": True,
            },
            "failed_agent_ids": [],
            "folders": [
                "media",
                "share",
            ],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Test 2",
            "with_automatic_settings": None,
        },
        {
            "addons": [
                {
                    "name": "Test",
                    "slug": "test",
                    "version": "1.0.0",
                },
            ],
            "agents": {"test.remote": {"protected": False, "size": 0}},
            "backup_id": "backup3",
            "database_included": True,
            "date": "1970-01-01T00:00:00.000Z",
            "extra_metadata": {
                "instance_id": "our_uuid",
                "with_automatic_settings": True,
            },
            "failed_agent_ids": [],
            "folders": [
                "media",
                "share",
            ],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Test",
            "with_automatic_settings": True,
        },
    ]

    mock_agents = await setup_backup_integration(
        hass,
        remote_agents=["test.remote"],
        backups={"test.remote": [backup_1, backup_2, backup_3]},
    )

    ws_client = await hass_ws_client(hass)

    path_glob.return_value = []

    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()

    assert result["success"] is True
    assert result["result"] == {
        "backups": backups_info,
        "agent_errors": {},
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id(
        {"type": "backup/config/update", "retention": {"copies": 1, "days": None}}
    )
    result = await ws_client.receive_json()
    assert result["success"]

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    mock_agents["test.remote"].async_upload_backup.side_effect = exception
    with patch("pathlib.Path.open", mock_open(read_data=b"test")):
        await ws_client.send_json_auto_id(
            {"type": "backup/generate", "agent_ids": agent_ids}
        )
        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.CREATE_BACKUP,
            "stage": None,
            "reason": None,
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
        "reason": None,
        "stage": CreateBackupStage.HOME_ASSISTANT,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
        "stage": CreateBackupStage.UPLOAD_TO_AGENTS,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": "upload_failed",
        "stage": None,
        "state": CreateBackupState.FAILED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    new_expected_backup_data = {
        "addons": [],
        "agents": {"backup.local": {"protected": False, "size": 123}},
        "backup_id": "abc123",
        "database_included": True,
        "date": ANY,
        "extra_metadata": {"instance_id": "our_uuid", "with_automatic_settings": False},
        "failed_agent_ids": ["test.remote"],
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2025.1.0",
        "name": "Custom backup 2025.1.0",
        "with_automatic_settings": False,
    }

    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()
    backups_response = result["result"].pop("backups")

    assert len(backups_response) == 4
    assert new_expected_backup_data in backups_response
    assert result["result"] == {
        "agent_errors": {},
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
        "last_action_event": {
            "manager_state": "create_backup",
            "reason": "upload_failed",
            "stage": None,
            "state": "failed",
        },
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await hass.async_block_till_done()
    assert hass_storage[DOMAIN]["data"]["backups"] == [
        {
            "backup_id": "abc123",
            "failed_agent_ids": ["test.remote"],
        }
    ]

    # one of the two matching backups with the remote agent should have been deleted
    assert mock_agents["test.remote"].async_delete_backup.call_count == 1


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
    await setup_backup_integration(hass)

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


async def delayed_boom(*args, **kwargs) -> tuple[NewBackup, Any]:
    """Raise an exception after a delay."""

    async def delayed_boom() -> None:
        await asyncio.sleep(0)
        raise Exception("Boom!")  # noqa: TRY002

    return (NewBackup(backup_job_id="abc123"), delayed_boom())


@pytest.mark.parametrize(
    (
        "automatic_agents",
        "create_backup_command",
        "create_backup_side_effect",
        "upload_side_effect",
        "create_backup_result",
        "issues_after_create_backup",
    ),
    [
        # No error
        (
            ["test.remote"],
            {"type": "backup/generate", "agent_ids": ["test.remote"]},
            None,
            None,
            True,
            {},
        ),
        (
            ["test.remote"],
            {"type": "backup/generate_with_automatic_settings"},
            None,
            None,
            True,
            {},
        ),
        # One agent unavailable
        (
            ["test.remote", "test.unknown"],
            {"type": "backup/generate", "agent_ids": ["test.remote", "test.unknown"]},
            None,
            None,
            True,
            {
                (DOMAIN, "automatic_backup_agents_unavailable_test.unknown"): {
                    "translation_key": "automatic_backup_agents_unavailable",
                    "translation_placeholders": {
                        "agent_id": "test.unknown",
                        "backup_settings": "/config/backup/settings",
                    },
                },
            },
        ),
        (
            ["test.remote", "test.unknown"],
            {"type": "backup/generate_with_automatic_settings"},
            None,
            None,
            True,
            {
                (DOMAIN, "automatic_backup_failed"): {
                    "translation_key": "automatic_backup_failed_upload_agents",
                    "translation_placeholders": {"failed_agents": "test.unknown"},
                },
                (DOMAIN, "automatic_backup_agents_unavailable_test.unknown"): {
                    "translation_key": "automatic_backup_agents_unavailable",
                    "translation_placeholders": {
                        "agent_id": "test.unknown",
                        "backup_settings": "/config/backup/settings",
                    },
                },
            },
        ),
        # Error raised in async_initiate_backup
        (
            ["test.remote"],
            {"type": "backup/generate", "agent_ids": ["test.remote"]},
            Exception("Boom!"),
            None,
            False,
            {},
        ),
        (
            ["test.remote"],
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
            ["test.remote"],
            {"type": "backup/generate", "agent_ids": ["test.remote"]},
            delayed_boom,
            None,
            True,
            {},
        ),
        (
            ["test.remote"],
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
            ["test.remote"],
            {"type": "backup/generate", "agent_ids": ["test.remote"]},
            None,
            Exception("Boom!"),
            True,
            {},
        ),
        (
            ["test.remote"],
            {"type": "backup/generate_with_automatic_settings"},
            None,
            Exception("Boom!"),
            True,
            {
                (DOMAIN, "automatic_backup_failed"): {
                    "translation_key": "automatic_backup_failed_upload_agents",
                    "translation_placeholders": {"failed_agents": "remote"},
                }
            },
        ),
    ],
)
async def test_create_backup_failure_raises_issue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    create_backup: AsyncMock,
    automatic_agents: list[str],
    create_backup_command: dict[str, Any],
    create_backup_side_effect: Exception | None,
    upload_side_effect: Exception | None,
    create_backup_result: bool,
    issues_after_create_backup: dict[tuple[str, str], dict[str, Any]],
) -> None:
    """Test backup issue is cleared after backup is created."""
    mock_agents = await setup_backup_integration(hass, remote_agents=["test.remote"])

    ws_client = await hass_ws_client(hass)

    create_backup.side_effect = create_backup_side_effect

    await ws_client.send_json_auto_id(
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": automatic_agents},
        }
    )
    result = await ws_client.receive_json()
    assert result["success"] is True

    mock_agents["test.remote"].async_upload_backup.side_effect = upload_side_effect
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


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    "exception", [BackupReaderWriterError("Boom!"), BaseException("Boom!")]
)
async def test_initiate_backup_non_agent_upload_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    generate_backup_id: MagicMock,
    path_glob: MagicMock,
    hass_storage: dict[str, Any],
    exception: Exception,
) -> None:
    """Test an unknown or writer upload error during backup generation."""
    agent_ids = [LOCAL_AGENT_ID, "test.remote"]
    mock_agents = await setup_backup_integration(hass, remote_agents=["test.remote"])

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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    mock_agents["test.remote"].async_upload_backup.side_effect = exception
    with patch("pathlib.Path.open", mock_open(read_data=b"test")):
        await ws_client.send_json_auto_id(
            {"type": "backup/generate", "agent_ids": agent_ids}
        )
        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.CREATE_BACKUP,
            "reason": None,
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
        "reason": None,
        "stage": CreateBackupStage.HOME_ASSISTANT,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
        "stage": CreateBackupStage.UPLOAD_TO_AGENTS,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": "upload_failed",
        "stage": None,
        "state": CreateBackupState.FAILED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    assert DOMAIN not in hass_storage


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    "exception", [BackupReaderWriterError("Boom!"), Exception("Boom!")]
)
async def test_initiate_backup_with_task_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    generate_backup_id: MagicMock,
    path_glob: MagicMock,
    create_backup: AsyncMock,
    exception: Exception,
) -> None:
    """Test backup task error during backup generation."""
    backup_task: asyncio.Future[Any] = asyncio.Future()
    backup_task.set_exception(exception)
    create_backup.return_value = (NewBackup(backup_job_id="abc123"), backup_task)
    agent_ids = [LOCAL_AGENT_ID, "test.remote"]

    await setup_backup_integration(hass, remote_agents=["test.remote"])

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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    await ws_client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": agent_ids}
    )
    await hass.async_block_till_done()

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
        "stage": None,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": "upload_failed",
        "stage": None,
        "state": CreateBackupState.FAILED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    backup_id = result["result"]["backup_job_id"]
    assert backup_id == generate_backup_id.return_value


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    (
        "open_call_count",
        "open_exception",
        "read_call_count",
        "read_exception",
        "close_call_count",
        "close_exception",
        "unlink_call_count",
        "unlink_exception",
    ),
    [
        (1, OSError("Boom!"), 0, None, 0, None, 1, None),
        (1, None, 1, OSError("Boom!"), 1, None, 1, None),
        (1, None, 1, None, 1, OSError("Boom!"), 1, None),
        (1, None, 1, None, 1, None, 1, OSError("Boom!")),
    ],
)
async def test_initiate_backup_file_error_upload_to_agents(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    generate_backup_id: MagicMock,
    path_glob: MagicMock,
    open_call_count: int,
    open_exception: Exception | None,
    read_call_count: int,
    read_exception: Exception | None,
    close_call_count: int,
    close_exception: Exception | None,
    unlink_call_count: int,
    unlink_exception: Exception | None,
) -> None:
    """Test file error during generate backup, while uploading to agents."""
    agent_ids = ["test.remote"]

    await setup_backup_integration(hass, remote_agents=["test.remote"])

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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    open_mock = mock_open(read_data=b"test")
    open_mock.side_effect = open_exception
    open_mock.return_value.read.side_effect = read_exception
    open_mock.return_value.close.side_effect = close_exception

    with (
        patch("pathlib.Path.open", open_mock),
        patch("pathlib.Path.unlink", side_effect=unlink_exception) as unlink_mock,
    ):
        await ws_client.send_json_auto_id(
            {"type": "backup/generate", "agent_ids": agent_ids}
        )

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.CREATE_BACKUP,
            "reason": None,
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
        "reason": None,
        "stage": CreateBackupStage.HOME_ASSISTANT,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
        "stage": CreateBackupStage.UPLOAD_TO_AGENTS,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": "upload_failed",
        "stage": None,
        "state": CreateBackupState.FAILED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    assert open_mock.call_count == open_call_count
    assert open_mock.return_value.read.call_count == read_call_count
    assert open_mock.return_value.close.call_count == close_call_count
    assert unlink_mock.call_count == unlink_call_count


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    (
        "mkdir_call_count",
        "mkdir_exception",
        "atomic_contents_add_call_count",
        "atomic_contents_add_exception",
        "stat_call_count",
        "stat_exception",
        "error_message",
    ),
    [
        (1, OSError("Boom!"), 0, None, 0, None, "Failed to create dir"),
        (1, None, 1, OSError("Boom!"), 0, None, "Boom!"),
        (1, None, 1, None, 1, OSError("Boom!"), "Error getting size"),
    ],
)
async def test_initiate_backup_file_error_create_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    generate_backup_id: MagicMock,
    path_glob: MagicMock,
    caplog: pytest.LogCaptureFixture,
    mkdir_call_count: int,
    mkdir_exception: Exception | None,
    atomic_contents_add_call_count: int,
    atomic_contents_add_exception: Exception | None,
    stat_call_count: int,
    stat_exception: Exception | None,
    error_message: str,
) -> None:
    """Test file error during generate backup, while creating backup."""
    agent_ids = ["test.remote"]

    await setup_backup_integration(hass, remote_agents=["test.remote"])

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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    with (
        patch(
            "homeassistant.components.backup.manager.atomic_contents_add",
            side_effect=atomic_contents_add_exception,
        ) as atomic_contents_add_mock,
        patch("pathlib.Path.mkdir", side_effect=mkdir_exception) as mkdir_mock,
        patch("pathlib.Path.stat", side_effect=stat_exception) as stat_mock,
    ):
        await ws_client.send_json_auto_id(
            {"type": "backup/generate", "agent_ids": agent_ids}
        )

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.CREATE_BACKUP,
            "reason": None,
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
        "reason": None,
        "stage": CreateBackupStage.HOME_ASSISTANT,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": "upload_failed",
        "stage": None,
        "state": CreateBackupState.FAILED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    assert atomic_contents_add_mock.call_count == atomic_contents_add_call_count
    assert mkdir_mock.call_count == mkdir_call_count
    assert stat_mock.call_count == stat_call_count

    assert error_message in caplog.text


def _mock_local_backup_agent(name: str) -> Mock:
    local_agent = mock_backup_agent(name)
    # This makes the local_agent pass isinstance checks for LocalBackupAgent
    local_agent.mock_add_spec(LocalBackupAgent)
    return local_agent


@pytest.mark.parametrize(
    ("agent_creator", "num_local_agents"),
    [(_mock_local_backup_agent, 2), (mock_backup_agent, 1)],
)
async def test_loading_platform_with_listener(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    agent_creator: Callable[[str], Mock],
    num_local_agents: int,
) -> None:
    """Test loading a backup agent platform which can be listened to."""
    ws_client = await hass_ws_client(hass)
    await setup_backup_integration(hass)
    manager = hass.data[DATA_MANAGER]

    get_agents_mock = AsyncMock(return_value=[agent_creator("remote1")])
    register_listener_mock = Mock()

    await setup_backup_platform(
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
        {"agent_id": "backup.local", "name": "local"},
        {"agent_id": "test.remote1", "name": "remote1"},
    ]
    assert len(manager.local_backup_agents) == num_local_agents

    get_agents_mock.assert_called_once_with(hass)
    register_listener_mock.assert_called_once_with(hass, listener=ANY)

    get_agents_mock.reset_mock()
    get_agents_mock.return_value = [agent_creator("remote2")]
    listener = register_listener_mock.call_args[1]["listener"]
    listener()

    get_agents_mock.assert_called_once_with(hass)
    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local", "name": "local"},
        {"agent_id": "test.remote2", "name": "remote2"},
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
    await setup_backup_platform(
        hass,
        domain="test",
        platform=platform_mock,
    )
    await setup_backup_integration(hass)

    assert platform_mock.mock_calls == []


async def test_exception_platform_pre(hass: HomeAssistant) -> None:
    """Test exception in pre step."""

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    remote_agent = mock_backup_agent("remote")
    await setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_pre_backup=_mock_step,
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
        ),
    )
    await setup_backup_integration(hass)

    with pytest.raises(BackupManagerError) as err:
        await hass.services.async_call(
            DOMAIN,
            "create",
            blocking=True,
        )

    assert str(err.value) == "Error during pre-backup: Test exception"


@pytest.mark.parametrize(
    ("unhandled_error", "expected_exception", "expected_msg"),
    [
        (None, BackupManagerError, "Error during post-backup: Test exception"),
        (
            HomeAssistantError("Boom"),
            BackupManagerExceptionGroup,
            (
                "Multiple errors when creating backup: Error during pre-backup: Boom, "
                "Error during post-backup: Test exception (2 sub-exceptions)"
            ),
        ),
        (
            Exception("Boom"),
            BackupManagerExceptionGroup,
            (
                "Multiple errors when creating backup: Error during pre-backup: Boom, "
                "Error during post-backup: Test exception (2 sub-exceptions)"
            ),
        ),
    ],
)
@pytest.mark.usefixtures("mock_backup_generation")
async def test_exception_platform_post(
    hass: HomeAssistant,
    unhandled_error: Exception | None,
    expected_exception: type[Exception],
    expected_msg: str,
) -> None:
    """Test exception in post step."""

    remote_agent = mock_backup_agent("remote")
    await setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            # We let the pre_backup fail to test that unhandled errors are not discarded
            # when post backup fails
            async_pre_backup=AsyncMock(side_effect=unhandled_error),
            async_post_backup=AsyncMock(
                side_effect=HomeAssistantError("Test exception")
            ),
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
        ),
    )
    await setup_backup_integration(hass)

    with pytest.raises(expected_exception, match=re.escape(expected_msg)):
        await hass.services.async_call(
            DOMAIN,
            "create",
            blocking=True,
        )


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
            ["Test_1970-01-01_00.00_00000000.tar"],
            {TEST_BACKUP_ABC123.backup_id: (TEST_BACKUP_ABC123, b"test")},
            b"test",
            0,
        ),
        (
            "agent_id=backup.local",
            1,
            1,
            ["Test_1970-01-01_00.00_00000000.tar"],
            {},
            None,
            0,
        ),
        (
            "agent_id=test.remote",
            2,
            0,
            [],
            {TEST_BACKUP_ABC123.backup_id: (TEST_BACKUP_ABC123, b"test")},
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
    mock_agents = await setup_backup_integration(hass, remote_agents=["test.remote"])
    client = await hass_client()

    upload_data = "test"
    open_mock = mock_open(read_data=upload_data.encode(encoding="utf-8"))

    with (
        patch("pathlib.Path.open", open_mock),
        patch(
            "homeassistant.components.backup.manager.make_backup_dir"
        ) as make_backup_dir_mock,
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
    assert make_backup_dir_mock.call_count == move_call_count + 1
    assert move_mock.call_count == move_call_count
    for index, name in enumerate(move_path_names):
        assert move_mock.call_args_list[index].args[1].name == name
    remote_agent = mock_agents["test.remote"]
    for backup_id, (backup, expected_backup_data) in remote_agent_backups.items():
        assert await remote_agent.async_get_backup(backup_id) == backup
        backup_data = bytearray()
        async for chunk in await remote_agent.async_download_backup(backup_id):
            backup_data += chunk
        assert backup_data == expected_backup_data
    assert unlink_mock.call_count == temp_file_unlink_call_count


@pytest.mark.usefixtures("mock_backup_generation")
async def test_receive_backup_busy_manager(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    create_backup: AsyncMock,
) -> None:
    """Test receive backup with a busy manager."""
    new_backup = NewBackup(backup_job_id="time-123")
    backup_task: asyncio.Future[WrittenBackup] = asyncio.Future()
    create_backup.return_value = (new_backup, backup_task)
    await setup_backup_integration(hass)
    client = await hass_client()
    ws_client = await hass_ws_client(hass)

    upload_data = "test"

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})
    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": "idle"}

    result = await ws_client.receive_json()
    assert result["success"] is True

    await ws_client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["backup.local"]}
    )
    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": "create_backup",
        "reason": None,
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


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize("exception", [BackupAgentError("Boom!"), Exception("Boom!")])
async def test_receive_backup_agent_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    path_glob: MagicMock,
    hass_storage: dict[str, Any],
    exception: Exception,
) -> None:
    """Test upload error during backup receive."""
    backup_1 = replace(TEST_BACKUP_ABC123, backup_id="backup1")  # matching instance id
    backup_2 = replace(TEST_BACKUP_DEF456, backup_id="backup2")  # other instance id
    backup_3 = replace(TEST_BACKUP_ABC123, backup_id="backup3")  # matching instance id
    backups_info: list[dict[str, Any]] = [
        {
            "addons": [
                {
                    "name": "Test",
                    "slug": "test",
                    "version": "1.0.0",
                },
            ],
            "agents": {"test.remote": {"protected": False, "size": 0}},
            "backup_id": "backup1",
            "database_included": True,
            "date": "1970-01-01T00:00:00.000Z",
            "extra_metadata": {
                "instance_id": "our_uuid",
                "with_automatic_settings": True,
            },
            "failed_agent_ids": [],
            "folders": [
                "media",
                "share",
            ],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Test",
            "with_automatic_settings": True,
        },
        {
            "addons": [],
            "agents": {"test.remote": {"protected": False, "size": 1}},
            "backup_id": "backup2",
            "database_included": False,
            "date": "1980-01-01T00:00:00.000Z",
            "extra_metadata": {
                "instance_id": "unknown_uuid",
                "with_automatic_settings": True,
            },
            "failed_agent_ids": [],
            "folders": [
                "media",
                "share",
            ],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Test 2",
            "with_automatic_settings": None,
        },
        {
            "addons": [
                {
                    "name": "Test",
                    "slug": "test",
                    "version": "1.0.0",
                },
            ],
            "agents": {"test.remote": {"protected": False, "size": 0}},
            "backup_id": "backup3",
            "database_included": True,
            "date": "1970-01-01T00:00:00.000Z",
            "extra_metadata": {
                "instance_id": "our_uuid",
                "with_automatic_settings": True,
            },
            "failed_agent_ids": [],
            "folders": [
                "media",
                "share",
            ],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Test",
            "with_automatic_settings": True,
        },
    ]

    mock_agents = await setup_backup_integration(
        hass,
        remote_agents=["test.remote"],
        backups={"test.remote": [backup_1, backup_2, backup_3]},
    )

    client = await hass_client()
    ws_client = await hass_ws_client(hass)

    path_glob.return_value = []

    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()

    assert result["success"] is True
    assert result["result"] == {
        "backups": backups_info,
        "agent_errors": {},
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id(
        {"type": "backup/config/update", "retention": {"copies": 1, "days": None}}
    )
    result = await ws_client.receive_json()
    assert result["success"]

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    upload_data = "test"
    open_mock = mock_open(read_data=upload_data.encode(encoding="utf-8"))

    mock_agents["test.remote"].async_upload_backup.side_effect = exception
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
            "/api/backup/upload?agent_id=test.remote",
            data={"file": StringIO(upload_data)},
        )
        await hass.async_block_till_done()

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": None,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": ReceiveBackupStage.RECEIVE_FILE,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": ReceiveBackupStage.UPLOAD_TO_AGENTS,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": None,
        "state": ReceiveBackupState.COMPLETED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()

    assert result["success"] is True
    assert result["result"] == {
        "backups": backups_info,
        "agent_errors": {},
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
        "last_action_event": {
            "manager_state": "receive_backup",
            "reason": None,
            "stage": None,
            "state": "completed",
        },
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await hass.async_block_till_done()
    assert hass_storage[DOMAIN]["data"]["backups"] == [
        {
            "backup_id": "abc123",
            "failed_agent_ids": ["test.remote"],
        }
    ]

    assert resp.status == 201
    assert open_mock.call_count == 1
    assert move_mock.call_count == 0
    assert unlink_mock.call_count == 1
    assert mock_agents["test.remote"].async_delete_backup.call_count == 0


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize("exception", [asyncio.CancelledError("Boom!")])
async def test_receive_backup_non_agent_upload_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    path_glob: MagicMock,
    hass_storage: dict[str, Any],
    exception: Exception,
) -> None:
    """Test non agent upload error during backup receive."""
    mock_agents = await setup_backup_integration(hass, remote_agents=["test.remote"])

    client = await hass_client()
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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    upload_data = "test"
    open_mock = mock_open(read_data=upload_data.encode(encoding="utf-8"))

    mock_agents["test.remote"].async_upload_backup.side_effect = exception
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
            "/api/backup/upload?agent_id=test.remote",
            data={"file": StringIO(upload_data)},
        )
        await hass.async_block_till_done()

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": None,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": ReceiveBackupStage.RECEIVE_FILE,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": ReceiveBackupStage.UPLOAD_TO_AGENTS,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    assert DOMAIN not in hass_storage
    assert resp.status == 500
    assert open_mock.call_count == 1
    assert move_mock.call_count == 0
    assert unlink_mock.call_count == 0


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    (
        "open_call_count",
        "open_exception",
        "write_call_count",
        "write_exception",
        "close_call_count",
        "close_exception",
    ),
    [
        (1, OSError("Boom!"), 0, None, 0, None),
        (1, None, 1, OSError("Boom!"), 1, None),
        (1, None, 1, None, 1, OSError("Boom!")),
    ],
)
async def test_receive_backup_file_write_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    path_glob: MagicMock,
    open_call_count: int,
    open_exception: Exception | None,
    write_call_count: int,
    write_exception: Exception | None,
    close_call_count: int,
    close_exception: Exception | None,
) -> None:
    """Test file write error during backup receive."""
    await setup_backup_integration(hass, remote_agents=["test.remote"])

    client = await hass_client()
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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    upload_data = "test"
    open_mock = mock_open(read_data=upload_data.encode(encoding="utf-8"))
    open_mock.side_effect = open_exception
    open_mock.return_value.write.side_effect = write_exception
    open_mock.return_value.close.side_effect = close_exception

    with (
        patch("pathlib.Path.open", open_mock),
    ):
        resp = await client.post(
            "/api/backup/upload?agent_id=test.remote",
            data={"file": StringIO(upload_data)},
        )
        await hass.async_block_till_done()

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": None,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": ReceiveBackupStage.RECEIVE_FILE,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": "unknown_error",
        "stage": None,
        "state": ReceiveBackupState.FAILED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    assert resp.status == 500
    assert open_mock.call_count == open_call_count
    assert open_mock.return_value.write.call_count == write_call_count
    assert open_mock.return_value.close.call_count == close_call_count


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    "exception",
    [
        OSError("Boom!"),
        tarfile.TarError("Boom!"),
        json.JSONDecodeError("Boom!", "test", 1),
        KeyError("Boom!"),
    ],
)
async def test_receive_backup_read_tar_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    path_glob: MagicMock,
    exception: Exception,
) -> None:
    """Test read tar error during backup receive."""
    await setup_backup_integration(hass, remote_agents=["test.remote"])

    client = await hass_client()
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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    upload_data = "test"
    open_mock = mock_open(read_data=upload_data.encode(encoding="utf-8"))

    with (
        patch("pathlib.Path.open", open_mock),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            side_effect=exception,
        ) as read_backup,
    ):
        resp = await client.post(
            "/api/backup/upload?agent_id=test.remote",
            data={"file": StringIO(upload_data)},
        )
        await hass.async_block_till_done()

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": None,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": ReceiveBackupStage.RECEIVE_FILE,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": "unknown_error",
        "stage": None,
        "state": ReceiveBackupState.FAILED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    assert resp.status == 500
    assert read_backup.call_count == 1


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    (
        "open_call_count",
        "open_exception",
        "read_call_count",
        "read_exception",
        "close_call_count",
        "close_exception",
        "unlink_call_count",
        "unlink_exception",
        "final_state",
        "final_state_reason",
        "response_status",
    ),
    [
        (
            2,
            [DEFAULT, OSError("Boom!")],
            0,
            None,
            1,
            [DEFAULT, DEFAULT],
            1,
            None,
            ReceiveBackupState.COMPLETED,
            None,
            201,
        ),
        (
            2,
            [DEFAULT, DEFAULT],
            1,
            OSError("Boom!"),
            2,
            [DEFAULT, DEFAULT],
            1,
            None,
            ReceiveBackupState.COMPLETED,
            None,
            201,
        ),
        (
            2,
            [DEFAULT, DEFAULT],
            1,
            None,
            2,
            [DEFAULT, OSError("Boom!")],
            1,
            None,
            ReceiveBackupState.COMPLETED,
            None,
            201,
        ),
        (
            2,
            [DEFAULT, DEFAULT],
            1,
            None,
            2,
            [DEFAULT, DEFAULT],
            1,
            OSError("Boom!"),
            ReceiveBackupState.FAILED,
            "unknown_error",
            500,
        ),
    ],
)
async def test_receive_backup_file_read_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    path_glob: MagicMock,
    open_call_count: int,
    open_exception: list[Exception | None],
    read_call_count: int,
    read_exception: Exception | None,
    close_call_count: int,
    close_exception: list[Exception | None],
    unlink_call_count: int,
    unlink_exception: Exception | None,
    final_state: ReceiveBackupState,
    final_state_reason: str | None,
    response_status: int,
) -> None:
    """Test file read error during backup receive."""
    await setup_backup_integration(hass, remote_agents=["test.remote"])

    client = await hass_client()
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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    upload_data = "test"
    open_mock = mock_open(read_data=upload_data.encode(encoding="utf-8"))

    open_mock.side_effect = open_exception
    open_mock.return_value.read.side_effect = read_exception
    open_mock.return_value.close.side_effect = close_exception

    with (
        patch("pathlib.Path.open", open_mock),
        patch("pathlib.Path.unlink", side_effect=unlink_exception) as unlink_mock,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_BACKUP_ABC123,
        ),
    ):
        resp = await client.post(
            "/api/backup/upload?agent_id=test.remote",
            data={"file": StringIO(upload_data)},
        )
        await hass.async_block_till_done()

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": None,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": ReceiveBackupStage.RECEIVE_FILE,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": None,
        "stage": ReceiveBackupStage.UPLOAD_TO_AGENTS,
        "state": ReceiveBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.RECEIVE_BACKUP,
        "reason": final_state_reason,
        "stage": None,
        "state": final_state,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    assert resp.status == response_status
    assert open_mock.call_count == open_call_count
    assert open_mock.return_value.read.call_count == read_call_count
    assert open_mock.return_value.close.call_count == close_call_count
    assert unlink_mock.call_count == unlink_call_count


@pytest.mark.usefixtures("path_glob")
@pytest.mark.parametrize(
    (
        "agent_id",
        "backup_id",
        "password_param",
        "backup_path",
        "restore_database",
        "restore_homeassistant",
        "dir",
    ),
    [
        (
            LOCAL_AGENT_ID,
            TEST_BACKUP_ABC123.backup_id,
            {},
            TEST_BACKUP_PATH_ABC123,
            True,
            False,
            "backups",
        ),
        (
            LOCAL_AGENT_ID,
            TEST_BACKUP_DEF456.backup_id,
            {},
            TEST_BACKUP_PATH_DEF456,
            True,
            False,
            "backups",
        ),
        (
            LOCAL_AGENT_ID,
            TEST_BACKUP_ABC123.backup_id,
            {"password": "abc123"},
            TEST_BACKUP_PATH_ABC123,
            False,
            True,
            "backups",
        ),
        (
            "test.remote",
            TEST_BACKUP_ABC123.backup_id,
            {},
            TEST_BACKUP_PATH_ABC123,
            True,
            True,
            "tmp_backups",
        ),
    ],
)
async def test_restore_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    agent_id: str,
    backup_id: str,
    password_param: dict[str, str],
    backup_path: Path,
    restore_database: bool,
    restore_homeassistant: bool,
    dir: str,
) -> None:
    """Test restore backup."""
    password = password_param.get("password")
    await setup_backup_integration(
        hass,
        remote_agents=["test.remote"],
        backups={"test.remote": [TEST_BACKUP_ABC123]},
    )

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open"),
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
        patch(
            "homeassistant.components.backup.manager.validate_password"
        ) as validate_password_mock,
        patch(
            "homeassistant.components.backup.backup.read_backup",
            side_effect=mock_read_backup,
        ),
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": backup_id,
                "agent_id": agent_id,
                "restore_database": restore_database,
                "restore_homeassistant": restore_homeassistant,
            }
            | password_param
        )

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": None,
            "stage": None,
            "state": RestoreBackupState.IN_PROGRESS,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": None,
            "stage": None,
            "state": RestoreBackupState.CORE_RESTART,
        }

        # Note: The core restart is not tested here, in reality the following events
        # are not sent because the core restart closes the WS connection.
        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": None,
            "stage": None,
            "state": RestoreBackupState.COMPLETED,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {"manager_state": BackupManagerState.IDLE}

        result = await ws_client.receive_json()
        assert result["success"] is True

    full_backup_path = f"{hass.config.path()}/{dir}/{backup_path.name}"
    expected_restore_file = json.dumps(
        {
            "path": full_backup_path,
            "password": password,
            "remove_after_restore": agent_id != LOCAL_AGENT_ID,
            "restore_database": restore_database,
            "restore_homeassistant": restore_homeassistant,
        }
    )
    validate_password_mock.assert_called_once_with(Path(full_backup_path), password)
    assert mocked_write_text.call_args[0][0] == expected_restore_file
    assert mocked_service_call.called


@pytest.mark.usefixtures("path_glob")
@pytest.mark.parametrize(
    ("agent_id", "dir"), [(LOCAL_AGENT_ID, "backups"), ("test.remote", "tmp_backups")]
)
async def test_restore_backup_wrong_password(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    agent_id: str,
    dir: str,
) -> None:
    """Test restore backup wrong password."""
    password = "hunter2"
    await setup_backup_integration(
        hass,
        remote_agents=["test.remote"],
        backups={"test.remote": [TEST_BACKUP_ABC123]},
    )

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open"),
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
        patch(
            "homeassistant.components.backup.manager.validate_password"
        ) as validate_password_mock,
        patch(
            "homeassistant.components.backup.backup.read_backup",
            side_effect=mock_read_backup,
        ),
    ):
        validate_password_mock.return_value = False
        await ws_client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": TEST_BACKUP_ABC123.backup_id,
                "agent_id": agent_id,
                "password": password,
            }
        )

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": None,
            "stage": None,
            "state": RestoreBackupState.IN_PROGRESS,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": "password_incorrect",
            "stage": None,
            "state": RestoreBackupState.FAILED,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {"manager_state": BackupManagerState.IDLE}

        result = await ws_client.receive_json()
        assert not result["success"]
        assert result["error"]["code"] == "password_incorrect"

    backup_path = f"{hass.config.path()}/{dir}/abc123.tar"
    validate_password_mock.assert_called_once_with(Path(backup_path), password)
    mocked_write_text.assert_not_called()
    mocked_service_call.assert_not_called()


@pytest.mark.usefixtures("path_glob")
@pytest.mark.parametrize(
    ("parameters", "expected_error", "expected_reason"),
    [
        (
            {"backup_id": "no_such_backup"},
            f"Backup no_such_backup not found in agent {LOCAL_AGENT_ID}",
            "backup_manager_error",
        ),
        (
            {"restore_addons": ["blah"]},
            "Addons and folders are not supported in core restore",
            "backup_reader_writer_error",
        ),
        (
            {"restore_folders": [Folder.ADDONS]},
            "Addons and folders are not supported in core restore",
            "backup_reader_writer_error",
        ),
        (
            {"restore_database": False, "restore_homeassistant": False},
            "Home Assistant or database must be included in restore",
            "backup_reader_writer_error",
        ),
    ],
)
async def test_restore_backup_wrong_parameters(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    parameters: dict[str, Any],
    expected_error: str,
    expected_reason: str,
) -> None:
    """Test restore backup wrong parameters."""
    await setup_backup_integration(hass)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
        patch(
            "homeassistant.components.backup.backup.read_backup",
            side_effect=mock_read_backup,
        ),
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": TEST_BACKUP_ABC123.backup_id,
                "agent_id": LOCAL_AGENT_ID,
            }
            | parameters
        )

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": None,
            "stage": None,
            "state": RestoreBackupState.IN_PROGRESS,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": expected_reason,
            "stage": None,
            "state": RestoreBackupState.FAILED,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {"manager_state": BackupManagerState.IDLE}

        result = await ws_client.receive_json()
        assert not result["success"]
        assert result["error"]["code"] == "home_assistant_error"
        assert result["error"]["message"] == expected_error

    mocked_write_text.assert_not_called()
    mocked_service_call.assert_not_called()


@pytest.mark.usefixtures("mock_backup_generation")
async def test_restore_backup_when_busy(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test restore backup with busy manager."""
    await setup_backup_integration(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": [LOCAL_AGENT_ID]}
    )
    result = await ws_client.receive_json()

    assert result["success"] is True

    await ws_client.send_json_auto_id(
        {
            "type": "backup/restore",
            "backup_id": TEST_BACKUP_ABC123.backup_id,
            "agent_id": LOCAL_AGENT_ID,
        }
    )
    result = await ws_client.receive_json()

    assert result["success"] is False
    assert result["error"]["code"] == "home_assistant_error"
    assert result["error"]["message"] == "Backup manager busy: create_backup"


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    ("exception", "error_code", "error_message", "expected_reason"),
    [
        (
            BackupAgentError("Boom!"),
            "home_assistant_error",
            "Boom!",
            "backup_agent_error",
        ),
        (
            Exception("Boom!"),
            "unknown_error",
            "Unknown error",
            "unknown_error",
        ),
    ],
)
async def test_restore_backup_agent_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    exception: Exception,
    error_code: str,
    error_message: str,
    expected_reason: str,
) -> None:
    """Test restore backup with agent error."""
    mock_agents = await setup_backup_integration(
        hass,
        remote_agents=["test.remote"],
        backups={"test.remote": [TEST_BACKUP_ABC123]},
    )
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    mock_agents["test.remote"].async_download_backup.side_effect = exception
    with (
        patch("pathlib.Path.open"),
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": TEST_BACKUP_ABC123.backup_id,
                "agent_id": "test.remote",
            }
        )

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": None,
            "stage": None,
            "state": RestoreBackupState.IN_PROGRESS,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": expected_reason,
            "stage": None,
            "state": RestoreBackupState.FAILED,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {"manager_state": BackupManagerState.IDLE}

        result = await ws_client.receive_json()
        assert not result["success"]
        assert result["error"]["code"] == error_code
        assert result["error"]["message"] == error_message

    assert mock_agents["test.remote"].async_download_backup.call_count == 1
    assert mocked_write_text.call_count == 0
    assert mocked_service_call.call_count == 0


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    (
        "open_call_count",
        "open_exception",
        "write_call_count",
        "write_exception",
        "close_call_count",
        "close_exception",
        "write_text_call_count",
        "write_text_exception",
        "validate_password_call_count",
    ),
    [
        (
            1,
            OSError("Boom!"),
            0,
            None,
            0,
            None,
            0,
            None,
            0,
        ),
        (
            1,
            None,
            1,
            OSError("Boom!"),
            1,
            None,
            0,
            None,
            0,
        ),
        (
            1,
            None,
            1,
            None,
            1,
            OSError("Boom!"),
            0,
            None,
            0,
        ),
        (
            1,
            None,
            1,
            None,
            1,
            None,
            1,
            OSError("Boom!"),
            1,
        ),
    ],
)
async def test_restore_backup_file_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    open_call_count: int,
    open_exception: list[Exception | None],
    write_call_count: int,
    write_exception: Exception | None,
    close_call_count: int,
    close_exception: list[Exception | None],
    write_text_call_count: int,
    write_text_exception: Exception | None,
    validate_password_call_count: int,
) -> None:
    """Test restore backup with file error."""
    mock_agents = await setup_backup_integration(
        hass,
        remote_agents=["test.remote"],
        backups={"test.remote": [TEST_BACKUP_ABC123]},
    )
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    open_mock = mock_open()
    open_mock.side_effect = open_exception
    open_mock.return_value.write.side_effect = write_exception
    open_mock.return_value.close.side_effect = close_exception

    with (
        patch("pathlib.Path.open", open_mock),
        patch(
            "pathlib.Path.write_text", side_effect=write_text_exception
        ) as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
        patch(
            "homeassistant.components.backup.manager.validate_password"
        ) as validate_password_mock,
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": TEST_BACKUP_ABC123.backup_id,
                "agent_id": "test.remote",
            }
        )

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": None,
            "stage": None,
            "state": RestoreBackupState.IN_PROGRESS,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.RESTORE_BACKUP,
            "reason": "unknown_error",
            "stage": None,
            "state": RestoreBackupState.FAILED,
        }

        result = await ws_client.receive_json()
        assert result["event"] == {"manager_state": BackupManagerState.IDLE}

        result = await ws_client.receive_json()
        assert not result["success"]
        assert result["error"]["code"] == "unknown_error"
        assert result["error"]["message"] == "Unknown error"

    assert mock_agents["test.remote"].async_download_backup.call_count == 1
    assert validate_password_mock.call_count == validate_password_call_count
    assert open_mock.call_count == open_call_count
    assert open_mock.return_value.write.call_count == write_call_count
    assert open_mock.return_value.close.call_count == close_call_count
    assert mocked_write_text.call_count == write_text_call_count
    assert mocked_service_call.call_count == 0


@pytest.mark.parametrize(
    ("commands", "agent_ids", "password", "protected_backup", "inner_tar_key"),
    [
        (
            [],
            ["backup.local", "test.remote"],
            None,
            {"backup.local": False, "test.remote": False},
            None,
        ),
        (
            [],
            ["backup.local", "test.remote"],
            "hunter2",
            {"backup.local": True, "test.remote": True},
            password_to_key("hunter2"),
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "backup.local": {"protected": False},
                        "test.remote": {"protected": False},
                    },
                }
            ],
            ["backup.local", "test.remote"],
            "hunter2",
            {"backup.local": False, "test.remote": False},
            None,  # None of the agents are protected
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "backup.local": {"protected": False},
                        "test.remote": {"protected": True},
                    },
                }
            ],
            ["backup.local", "test.remote"],
            "hunter2",
            {"backup.local": False, "test.remote": True},
            None,  # Local agent is not protected
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "backup.local": {"protected": True},
                        "test.remote": {"protected": False},
                    },
                }
            ],
            ["backup.local", "test.remote"],
            "hunter2",
            {"backup.local": True, "test.remote": False},
            password_to_key("hunter2"),  # Local agent is protected
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "backup.local": {"protected": True},
                        "test.remote": {"protected": True},
                    },
                }
            ],
            ["backup.local", "test.remote"],
            "hunter2",
            {"backup.local": True, "test.remote": True},
            password_to_key("hunter2"),
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "backup.local": {"protected": False},
                        "test.remote": {"protected": True},
                    },
                }
            ],
            ["backup.local", "test.remote"],
            None,
            {"backup.local": False, "test.remote": False},
            None,  # No password supplied
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "backup.local": {"protected": False},
                        "test.remote": {"protected": True},
                    },
                }
            ],
            ["test.remote"],
            "hunter2",
            {"test.remote": True},
            password_to_key("hunter2"),
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "backup.local": {"protected": False},
                        "test.remote": {"protected": False},
                    },
                }
            ],
            ["test.remote"],
            "hunter2",
            {"test.remote": False},
            password_to_key("hunter2"),  # Temporary backup protected when password set
        ),
    ],
)
@pytest.mark.usefixtures("mock_backup_generation")
async def test_initiate_backup_per_agent_encryption(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    generate_backup_id: MagicMock,
    mocked_tarfile: Mock,
    path_glob: MagicMock,
    commands: dict[str, Any],
    agent_ids: list[str],
    password: str | None,
    protected_backup: dict[str, bool],
    inner_tar_key: bytes | None,
) -> None:
    """Test generate backup where encryption is selectively set on agents."""
    await setup_backup_integration(hass, remote_agents=["test.remote"])

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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    for command in commands:
        await ws_client.send_json_auto_id(command)
        result = await ws_client.receive_json()
        assert result["success"] is True

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    result = await ws_client.receive_json()
    assert result["success"] is True

    with (
        patch("pathlib.Path.open", mock_open(read_data=b"test")),
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "backup/generate",
                "agent_ids": agent_ids,
                "password": password,
                "name": "test",
            }
        )
        result = await ws_client.receive_json()
        assert result["event"] == {
            "manager_state": BackupManagerState.CREATE_BACKUP,
            "reason": None,
            "stage": None,
            "state": CreateBackupState.IN_PROGRESS,
        }
        result = await ws_client.receive_json()
        assert result["success"] is True

        backup_id = result["result"]["backup_job_id"]
        assert backup_id == generate_backup_id.return_value

        await hass.async_block_till_done()

    mocked_tarfile.return_value.create_inner_tar.assert_called_once_with(
        ANY, gzip=True, key=inner_tar_key
    )

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
        "stage": CreateBackupStage.HOME_ASSISTANT,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
        "stage": CreateBackupStage.UPLOAD_TO_AGENTS,
        "state": CreateBackupState.IN_PROGRESS,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {
        "manager_state": BackupManagerState.CREATE_BACKUP,
        "reason": None,
        "stage": None,
        "state": CreateBackupState.COMPLETED,
    }

    result = await ws_client.receive_json()
    assert result["event"] == {"manager_state": BackupManagerState.IDLE}

    await ws_client.send_json_auto_id(
        {"type": "backup/details", "backup_id": backup_id}
    )
    result = await ws_client.receive_json()

    backup_data = result["result"]["backup"]

    assert backup_data == {
        "addons": [],
        "agents": {
            agent_id: {"protected": protected_backup[agent_id], "size": ANY}
            for agent_id in agent_ids
        },
        "backup_id": backup_id,
        "database_included": True,
        "date": ANY,
        "extra_metadata": {"instance_id": "our_uuid", "with_automatic_settings": False},
        "failed_agent_ids": [],
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2025.1.0",
        "name": "test",
        "with_automatic_settings": False,
    }


@pytest.mark.parametrize(
    ("restore_result", "last_action_event"),
    [
        (
            {"error": None, "error_type": None, "success": True},
            {
                "manager_state": "restore_backup",
                "reason": None,
                "stage": None,
                "state": "completed",
            },
        ),
        (
            {"error": "Boom!", "error_type": "ValueError", "success": False},
            {
                "manager_state": "restore_backup",
                "reason": "Boom!",
                "stage": None,
                "state": "failed",
            },
        ),
    ],
)
async def test_restore_progress_after_restart(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    restore_result: dict[str, Any],
    last_action_event: dict[str, Any],
) -> None:
    """Test restore backup progress after restart."""

    with patch(
        "pathlib.Path.read_bytes", return_value=json.dumps(restore_result).encode()
    ):
        await setup_backup_integration(hass)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()
    assert result["success"] is True
    assert result["result"] == {
        "agent_errors": {},
        "backups": [],
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
        "last_action_event": last_action_event,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }


async def test_restore_progress_after_restart_fail_to_remove(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test restore backup progress after restart when failing to remove result file."""

    with patch("pathlib.Path.unlink", side_effect=OSError("Boom!")):
        await setup_backup_integration(hass)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()
    assert result["success"] is True
    assert result["result"] == {
        "agent_errors": {},
        "backups": [],
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }

    assert (
        "Unexpected error deleting backup restore result file: <class 'OSError'> Boom!"
        in caplog.text
    )


async def test_manager_blocked_until_home_assistant_started(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test backup manager's state is blocked until Home Assistant has started."""

    hass.set_state(CoreState.not_running)

    await setup_backup_integration(hass)
    manager = hass.data[DATA_MANAGER]

    assert manager.state == BackupManagerState.BLOCKED
    assert manager.last_action_event is None

    # Fired when Home Assistant changes to starting state
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert manager.state == BackupManagerState.BLOCKED
    assert manager.last_action_event is None

    # Fired when Home Assistant changes to running state
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert manager.state == BackupManagerState.IDLE
    assert manager.last_action_event is None


async def test_manager_not_blocked_after_restore(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test restore backup progress after restart."""
    restore_result = {"error": None, "error_type": None, "success": True}

    hass.set_state(CoreState.not_running)
    with patch(
        "pathlib.Path.read_bytes", return_value=json.dumps(restore_result).encode()
    ):
        await setup_backup_integration(hass)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id({"type": "backup/info"})
    result = await ws_client.receive_json()
    assert result["success"] is True
    assert result["result"] == {
        "agent_errors": {},
        "backups": [],
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
        "last_action_event": {
            "manager_state": "restore_backup",
            "reason": None,
            "stage": None,
            "state": "completed",
        },
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }
