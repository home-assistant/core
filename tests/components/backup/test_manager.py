"""Tests for the Backup integration."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import aiohttp
from multidict import CIMultiDict, CIMultiDictProxy
import pytest

from homeassistant.components.backup import BackupManager, BackupUploadMetadata
from homeassistant.components.backup.agent import BackupAgentPlatformProtocol
from homeassistant.components.backup.manager import (
    BackupPlatformProtocol,
    BackupProgress,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import TEST_BACKUP, BackupAgentTest

from tests.common import MockPlatform, mock_platform


async def _mock_backup_generation(
    manager: BackupManager, mocked_json_bytes: Mock, mocked_tarfile: Mock
) -> None:
    """Mock backup generator."""

    progress: list[BackupProgress] = []

    def on_progress(_progress: BackupProgress) -> None:
        """Mock progress callback."""
        progress.append(_progress)

    assert manager.backup_task is None
    await manager.async_create_backup(on_progress=on_progress)
    assert manager.backup_task is not None
    assert progress == []

    backup = await manager.backup_task
    assert progress == [BackupProgress(done=True, stage=None, success=True)]

    assert mocked_json_bytes.call_count == 1
    backup_json_dict = mocked_json_bytes.call_args[0][0]
    assert isinstance(backup_json_dict, dict)
    assert backup_json_dict["homeassistant"] == {"version": "2025.1.0"}
    assert manager.backup_dir.as_posix() in str(mocked_tarfile.call_args_list[0][0][0])

    return backup


async def _setup_mock_domain(
    hass: HomeAssistant,
    platform: BackupPlatformProtocol | BackupAgentPlatformProtocol | None = None,
) -> None:
    """Set up a mock domain."""
    mock_platform(hass, "some_domain.backup", platform or MockPlatform())
    assert await async_setup_component(hass, "some_domain", {})


async def test_constructor(hass: HomeAssistant) -> None:
    """Test BackupManager constructor."""
    manager = BackupManager(hass)
    assert manager.backup_dir.as_posix() == hass.config.path("backups")


async def test_load_backups(hass: HomeAssistant) -> None:
    """Test loading backups."""
    manager = BackupManager(hass)
    with (
        patch("pathlib.Path.glob", return_value=[TEST_BACKUP.path]),
        patch("tarfile.open", return_value=MagicMock()),
        patch(
            "homeassistant.components.backup.manager.json_loads_object",
            return_value={
                "slug": TEST_BACKUP.slug,
                "name": TEST_BACKUP.name,
                "date": TEST_BACKUP.date,
            },
        ),
        patch(
            "pathlib.Path.stat",
            return_value=MagicMock(st_size=TEST_BACKUP.size),
        ),
    ):
        await manager.load_backups()
    backups = await manager.async_get_backups()
    assert backups == {TEST_BACKUP.slug: TEST_BACKUP}


async def test_load_backups_with_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backups with exception."""
    manager = BackupManager(hass)
    with (
        patch("pathlib.Path.glob", return_value=[TEST_BACKUP.path]),
        patch("tarfile.open", side_effect=OSError("Test exception")),
    ):
        await manager.load_backups()
    backups = await manager.async_get_backups()
    assert f"Unable to read backup {TEST_BACKUP.path}: Test exception" in caplog.text
    assert backups == {}


async def test_removing_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing backup."""
    manager = BackupManager(hass)
    manager.backups = {TEST_BACKUP.slug: TEST_BACKUP}
    manager.loaded_backups = True

    with patch("pathlib.Path.exists", return_value=True):
        await manager.async_remove_backup(slug=TEST_BACKUP.slug)
    assert "Removed backup located at" in caplog.text


async def test_removing_non_existing_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing not existing backup."""
    manager = BackupManager(hass)

    await manager.async_remove_backup(slug="non_existing")
    assert "Removed backup located at" not in caplog.text


async def test_getting_backup_that_does_not_exist(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting backup that does not exist."""
    manager = BackupManager(hass)
    manager.backups = {TEST_BACKUP.slug: TEST_BACKUP}
    manager.loaded_backups = True

    with patch("pathlib.Path.exists", return_value=False):
        backup = await manager.async_get_backup(slug=TEST_BACKUP.slug)
        assert backup is None

        assert (
            f"Removing tracked backup ({TEST_BACKUP.slug}) that "
            f"does not exists on the expected path {TEST_BACKUP.path}"
        ) in caplog.text


async def test_async_create_backup_when_backing_up(hass: HomeAssistant) -> None:
    """Test generate backup."""
    event = asyncio.Event()
    manager = BackupManager(hass)
    manager.backup_task = hass.async_create_task(event.wait())
    with pytest.raises(HomeAssistantError, match="Backup already in progress"):
        await manager.async_create_backup(on_progress=None)
    event.set()


@pytest.mark.usefixtures("mock_backup_generation")
async def test_async_create_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
) -> None:
    """Test generate backup."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    await _mock_backup_generation(manager, mocked_json_bytes, mocked_tarfile)

    assert "Generated new backup with slug " in caplog.text
    assert "Creating backup directory" in caplog.text
    assert "Loaded 0 platforms" in caplog.text
    assert "Loaded 0 agents" in caplog.text


async def test_loading_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass)

    assert not manager.loaded_platforms
    assert not manager.platforms

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(),
        ),
    )
    await manager.load_platforms()
    await hass.async_block_till_done()

    assert manager.loaded_platforms
    assert len(manager.platforms) == 1

    assert "Loaded 1 platforms" in caplog.text


async def test_loading_agents(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup agents."""
    manager = BackupManager(hass)

    assert not manager.loaded_platforms
    assert not manager.platforms

    await _setup_mock_domain(
        hass,
        Mock(
            async_get_backup_agents=AsyncMock(return_value=[BackupAgentTest("test")]),
        ),
    )
    await manager.load_platforms()
    await hass.async_block_till_done()

    assert manager.loaded_platforms
    assert len(manager.backup_agents) == 1

    assert "Loaded 1 agents" in caplog.text
    assert "some_domain.test" in manager.backup_agents


async def test_not_loading_bad_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass)

    assert not manager.loaded_platforms
    assert not manager.platforms

    await _setup_mock_domain(hass)
    await manager.load_platforms()
    await hass.async_block_till_done()

    assert manager.loaded_platforms
    assert len(manager.platforms) == 0

    assert "Loaded 0 platforms" in caplog.text


@pytest.mark.usefixtures("mock_backup_generation")
async def test_syncing_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
) -> None:
    """Test syncing a backup."""
    manager = BackupManager(hass)

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(
                return_value=[
                    BackupAgentTest("agent1"),
                    BackupAgentTest("agent2"),
                ]
            ),
        ),
    )
    await manager.load_platforms()
    await hass.async_block_till_done()

    backup = await _mock_backup_generation(manager, mocked_json_bytes, mocked_tarfile)

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=backup,
        ),
        patch.object(BackupAgentTest, "async_upload_backup") as mocked_upload,
        patch(
            "homeassistant.components.backup.manager.HAVERSION",
            "2025.1.0",
        ),
    ):
        await manager.async_upload_backup(slug=backup.slug)
        assert mocked_upload.call_count == 2
        first_call = mocked_upload.call_args_list[0]
        assert first_call[1]["path"] == backup.path
        assert first_call[1]["metadata"] == BackupUploadMetadata(
            date=backup.date,
            homeassistant="2025.1.0",
            name=backup.name,
            size=backup.size,
            slug=backup.slug,
        )

    assert "Error during backup upload" not in caplog.text


@pytest.mark.usefixtures("mock_backup_generation")
async def test_syncing_backup_with_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
) -> None:
    """Test syncing a backup with exception."""
    manager = BackupManager(hass)

    class ModifiedBackupSyncAgentTest(BackupAgentTest):
        async def async_upload_backup(self, **kwargs: Any) -> None:
            raise HomeAssistantError("Test exception")

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(
                return_value=[
                    ModifiedBackupSyncAgentTest("agent1"),
                    ModifiedBackupSyncAgentTest("agent2"),
                ]
            ),
        ),
    )
    await manager.load_platforms()
    await hass.async_block_till_done()

    backup = await _mock_backup_generation(manager, mocked_json_bytes, mocked_tarfile)

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=backup,
        ),
        patch.object(
            ModifiedBackupSyncAgentTest,
            "async_upload_backup",
        ) as mocked_upload,
        patch(
            "homeassistant.components.backup.manager.HAVERSION",
            "2025.1.0",
        ),
    ):
        mocked_upload.side_effect = HomeAssistantError("Test exception")
        await manager.async_upload_backup(slug=backup.slug)
        assert mocked_upload.call_count == 2
        first_call = mocked_upload.call_args_list[0]
        assert first_call[1]["path"] == backup.path
        assert first_call[1]["metadata"] == BackupUploadMetadata(
            date=backup.date,
            homeassistant="2025.1.0",
            name=backup.name,
            size=backup.size,
            slug=backup.slug,
        )

    assert "Error during backup upload - Test exception" in caplog.text


@pytest.mark.usefixtures("mock_backup_generation")
async def test_syncing_backup_no_agents(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
) -> None:
    """Test syncing a backup with no agents."""
    manager = BackupManager(hass)

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(return_value=[]),
        ),
    )
    await manager.load_platforms()
    await hass.async_block_till_done()

    backup = await _mock_backup_generation(manager, mocked_json_bytes, mocked_tarfile)
    with patch(
        "homeassistant.components.backup.agent.BackupAgent.async_upload_backup"
    ) as mocked_async_upload_backup:
        await manager.async_upload_backup(slug=backup.slug)
        assert mocked_async_upload_backup.call_count == 0


async def test_exception_plaform_pre(
    hass: HomeAssistant, mocked_json_bytes: Mock, mocked_tarfile: Mock
) -> None:
    """Test exception in pre step."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=_mock_step,
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(),
        ),
    )

    with pytest.raises(HomeAssistantError):
        await _mock_backup_generation(manager, mocked_json_bytes, mocked_tarfile)


async def test_exception_plaform_post(
    hass: HomeAssistant, mocked_json_bytes: Mock, mocked_tarfile: Mock
) -> None:
    """Test exception in post step."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=_mock_step,
            async_get_backup_agents=AsyncMock(),
        ),
    )

    with pytest.raises(HomeAssistantError):
        await _mock_backup_generation(manager, mocked_json_bytes, mocked_tarfile)


async def test_loading_platforms_when_running_async_pre_backup_actions(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms when running post backup actions."""
    manager = BackupManager(hass)

    assert not manager.loaded_platforms
    assert not manager.platforms

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(),
        ),
    )
    await manager.async_pre_backup_actions()

    assert manager.loaded_platforms
    assert len(manager.platforms) == 1

    assert "Loaded 1 platforms" in caplog.text


async def test_loading_platforms_when_running_async_post_backup_actions(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms when running post backup actions."""
    manager = BackupManager(hass)

    assert not manager.loaded_platforms
    assert not manager.platforms

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(),
        ),
    )
    await manager.async_post_backup_actions()

    assert manager.loaded_platforms
    assert len(manager.platforms) == 1

    assert "Loaded 1 platforms" in caplog.text


async def test_async_receive_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test receiving a backup file."""
    manager = BackupManager(hass)

    size = 2 * 2**16
    protocol = Mock(_reading_paused=False)
    stream = aiohttp.StreamReader(protocol, 2**16)
    stream.feed_data(b"0" * size + b"\r\n--:--")
    stream.feed_eof()

    open_mock = mock_open()

    with patch("pathlib.Path.open", open_mock), patch("shutil.move") as mover_mock:
        await manager.async_receive_backup(
            contents=aiohttp.BodyPartReader(
                b"--:",
                CIMultiDictProxy(
                    CIMultiDict(
                        {
                            aiohttp.hdrs.CONTENT_DISPOSITION: "attachment; filename=abc123.tar"
                        }
                    )
                ),
                stream,
            )
        )
        assert open_mock.call_count == 1
        assert mover_mock.call_count == 1
        assert mover_mock.mock_calls[0].args[1].name == "abc123.tar"


async def test_async_trigger_restore(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test trigger restore."""
    manager = BackupManager(hass)
    manager.loaded_backups = True
    manager.backups = {TEST_BACKUP.slug: TEST_BACKUP}

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
    ):
        await manager.async_restore_backup(TEST_BACKUP.slug)
        assert mocked_write_text.call_args[0][0] == '{"path": "abc123.tar"}'
        assert mocked_service_call.called


async def test_async_trigger_restore_missing_backup(hass: HomeAssistant) -> None:
    """Test trigger restore."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    with pytest.raises(HomeAssistantError, match="Backup abc123 not found"):
        await manager.async_restore_backup(TEST_BACKUP.slug)
