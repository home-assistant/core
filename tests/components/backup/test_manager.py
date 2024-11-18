"""Tests for the Backup integration."""

from __future__ import annotations

import asyncio
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call, mock_open, patch

import aiohttp
from multidict import CIMultiDict, CIMultiDictProxy
import pytest

from homeassistant.components.backup import (
    DOMAIN,
    BackupAgentPlatformProtocol,
    BackupManager,
    BackupPlatformProtocol,
    backup as local_backup_platform,
)
from homeassistant.components.backup.manager import LOCAL_AGENT_ID, BackupProgress
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import (
    TEST_BACKUP,
    TEST_BACKUP_PATH,
    TEST_BASE_BACKUP,
    TEST_LOCAL_BACKUP,
    BackupAgentTest,
)

from tests.common import MockPlatform, mock_platform

_EXPECTED_FILES_WITH_DATABASE = {
    True: ["test.txt", ".storage", "home-assistant_v2.db"],
    False: ["test.txt", ".storage"],
}


async def _mock_backup_generation(
    hass: HomeAssistant,
    manager: BackupManager,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
    *,
    database_included: bool = True,
    name: str | None = "Core 2025.1.0",
    password: str | None = None,
) -> None:
    """Mock backup generator."""

    progress: list[BackupProgress] = []

    def on_progress(_progress: BackupProgress) -> None:
        """Mock progress callback."""
        progress.append(_progress)

    assert manager.backup_task is None
    await manager.async_create_backup(
        addons_included=[],
        agent_ids=[LOCAL_AGENT_ID],
        database_included=database_included,
        folders_included=[],
        name=name,
        on_progress=on_progress,
        password=password,
    )
    assert manager.backup_task is not None
    assert progress == []

    backup = await manager.backup_task
    assert progress == [BackupProgress(done=True, stage=None, success=True)]

    assert mocked_json_bytes.call_count == 1
    backup_json_dict = mocked_json_bytes.call_args[0][0]
    assert isinstance(backup_json_dict, dict)
    assert backup_json_dict == {
        "compressed": True,
        "date": ANY,
        "folders": ["homeassistant"],
        "homeassistant": {
            "exclude_database": not database_included,
            "version": "2025.1.0",
        },
        "name": name,
        "protected": bool(password),
        "slug": ANY,
        "type": "partial",
    }
    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    assert local_agent._backup_dir.as_posix() in str(
        mocked_tarfile.call_args_list[0][0][0]
    )
    outer_tar = mocked_tarfile.return_value
    core_tar = outer_tar.create_inner_tar.return_value.__enter__.return_value
    expected_files = [call(hass.config.path(), arcname="data", recursive=False)] + [
        call(file, arcname=f"data/{file}", recursive=False)
        for file in _EXPECTED_FILES_WITH_DATABASE[database_included]
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


async def test_constructor(hass: HomeAssistant) -> None:
    """Test BackupManager constructor."""
    manager = BackupManager(hass)
    assert manager.temp_backup_dir.as_posix() == hass.config.path("tmp_backups")


async def test_load_backups(hass: HomeAssistant) -> None:
    """Test loading backups."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    with (
        patch("pathlib.Path.glob", return_value=[TEST_BACKUP_PATH]),
        patch("tarfile.open", return_value=MagicMock()),
        patch(
            "homeassistant.components.backup.util.json_loads_object",
            return_value={
                "slug": TEST_LOCAL_BACKUP.slug,
                "name": TEST_LOCAL_BACKUP.name,
                "date": TEST_LOCAL_BACKUP.date,
            },
        ),
        patch(
            "pathlib.Path.stat",
            return_value=MagicMock(st_size=TEST_LOCAL_BACKUP.size),
        ),
    ):
        await manager.backup_agents[LOCAL_AGENT_ID].load_backups()
    backups, agent_errors = await manager.async_get_backups()
    assert backups == {TEST_BACKUP.slug: TEST_BACKUP}
    assert agent_errors == {}


async def test_load_backups_with_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backups with exception."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    with (
        patch("pathlib.Path.glob", return_value=[TEST_BACKUP_PATH]),
        patch("tarfile.open", side_effect=OSError("Test exception")),
    ):
        await manager.backup_agents[LOCAL_AGENT_ID].load_backups()
    backups, agent_errors = await manager.async_get_backups()
    assert f"Unable to read backup {TEST_BACKUP_PATH}: Test exception" in caplog.text
    assert backups == {}
    assert agent_errors == {}


async def test_removing_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing backup."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._backups = {TEST_LOCAL_BACKUP.slug: TEST_LOCAL_BACKUP}
    local_agent._loaded_backups = True

    with patch("pathlib.Path.exists", return_value=True):
        await manager.async_remove_backup(slug=TEST_LOCAL_BACKUP.slug)
    assert "Removed backup located at" in caplog.text


async def test_removing_non_existing_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing not existing backup."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    await manager.async_remove_backup(slug="non_existing")
    assert "Removed backup located at" not in caplog.text


async def test_getting_backup_that_does_not_exist(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting backup that does not exist."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._backups = {TEST_LOCAL_BACKUP.slug: TEST_LOCAL_BACKUP}
    local_agent._loaded_backups = True

    with patch("pathlib.Path.exists", return_value=False):
        backup, agent_errors = await manager.async_get_backup(
            slug=TEST_LOCAL_BACKUP.slug
        )
        assert backup is None
        assert agent_errors == {}

        assert (
            f"Removing tracked backup ({TEST_LOCAL_BACKUP.slug}) that "
            f"does not exists on the expected path {TEST_LOCAL_BACKUP.path}"
        ) in caplog.text


async def test_async_create_backup_when_backing_up(hass: HomeAssistant) -> None:
    """Test generate backup."""
    event = asyncio.Event()
    manager = BackupManager(hass)
    manager.backup_task = hass.async_create_task(event.wait())
    with pytest.raises(HomeAssistantError, match="Backup already in progress"):
        await manager.async_create_backup(
            addons_included=[],
            agent_ids=[LOCAL_AGENT_ID],
            database_included=True,
            folders_included=[],
            name=None,
            on_progress=None,
            password=None,
        )
    event.set()


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"database_included": True, "name": "abc123"},
        {"database_included": False},
        {"password": "abc123"},
    ],
)
async def test_async_create_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mocked_json_bytes: Mock,
    mocked_tarfile: Mock,
    params: dict,
) -> None:
    """Test generate backup."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._loaded_backups = True

    await _mock_backup_generation(
        hass, manager, mocked_json_bytes, mocked_tarfile, **params
    )

    assert "Generated new backup with slug " in caplog.text
    assert "Creating backup directory" in caplog.text
    assert "Loaded 0 platforms" in caplog.text
    assert "Loaded 1 agents" in caplog.text

    assert len(local_agent._backups) == 1
    backup = list(local_agent._backups.values())[0]
    assert backup.protected is bool(params.get("password"))


async def test_loading_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass)

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


async def test_loading_agents(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup agents."""
    manager = BackupManager(hass)

    assert not manager.platforms

    await _setup_backup_platform(
        hass,
        platform=Mock(
            async_get_backup_agents=AsyncMock(return_value=[BackupAgentTest("test")]),
        ),
    )
    await manager.load_platforms()
    await hass.async_block_till_done()

    assert len(manager.backup_agents) == 1

    assert "Loaded 1 agents" in caplog.text
    assert "some_domain.test" in manager.backup_agents


async def test_not_loading_bad_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass)

    assert not manager.platforms

    await _setup_backup_platform(hass)
    await manager.load_platforms()
    await hass.async_block_till_done()

    assert len(manager.platforms) == 0

    assert "Loaded 0 platforms" in caplog.text


async def test_exception_plaform_pre(
    hass: HomeAssistant, mocked_json_bytes: Mock, mocked_tarfile: Mock
) -> None:
    """Test exception in pre step."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    await _setup_backup_platform(
        hass,
        platform=Mock(
            async_pre_backup=_mock_step,
            async_post_backup=AsyncMock(),
            async_get_backup_agents=AsyncMock(),
        ),
    )

    with pytest.raises(HomeAssistantError):
        await _mock_backup_generation(hass, manager, mocked_json_bytes, mocked_tarfile)


async def test_exception_plaform_post(
    hass: HomeAssistant, mocked_json_bytes: Mock, mocked_tarfile: Mock
) -> None:
    """Test exception in post step."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    await _setup_backup_platform(
        hass,
        platform=Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=_mock_step,
            async_get_backup_agents=AsyncMock(),
        ),
    )

    with pytest.raises(HomeAssistantError):
        await _mock_backup_generation(hass, manager, mocked_json_bytes, mocked_tarfile)


async def test_async_receive_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test receiving a backup file."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    size = 2 * 2**16
    protocol = Mock(_reading_paused=False)
    stream = aiohttp.StreamReader(protocol, 2**16)
    stream.feed_data(b"0" * size + b"\r\n--:--")
    stream.feed_eof()

    open_mock = mock_open()

    with (
        patch("pathlib.Path.open", open_mock),
        patch("shutil.copy") as copy_mock,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_BASE_BACKUP,
        ),
    ):
        await manager.async_receive_backup(
            agent_ids=[LOCAL_AGENT_ID],
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
            ),
        )
        assert open_mock.call_count == 1
        assert copy_mock.call_count == 1
        assert copy_mock.mock_calls[0].args[1].name == "abc123.tar"


async def test_async_trigger_restore(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test trigger restore."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._backups = {TEST_LOCAL_BACKUP.slug: TEST_LOCAL_BACKUP}
    local_agent._loaded_backups = True

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
    ):
        await manager.async_restore_backup(
            TEST_LOCAL_BACKUP.slug, agent_id=LOCAL_AGENT_ID, password=None
        )
        assert (
            mocked_write_text.call_args[0][0]
            == f'{{"path": "{hass.config.path()}/backups/abc123.tar", "password": null}}'
        )
        assert mocked_service_call.called


async def test_async_trigger_restore_with_password(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test trigger restore."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._backups = {TEST_LOCAL_BACKUP.slug: TEST_LOCAL_BACKUP}
    local_agent._loaded_backups = True

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.write_text") as mocked_write_text,
        patch("homeassistant.core.ServiceRegistry.async_call") as mocked_service_call,
    ):
        await manager.async_restore_backup(
            slug=TEST_LOCAL_BACKUP.slug, agent_id=LOCAL_AGENT_ID, password="abc123"
        )
        assert (
            mocked_write_text.call_args[0][0]
            == f'{{"path": "{hass.config.path()}/backups/abc123.tar", "password": "abc123"}}'
        )
        assert mocked_service_call.called


async def test_async_trigger_restore_missing_backup(hass: HomeAssistant) -> None:
    """Test trigger restore."""
    manager = BackupManager(hass)

    await _setup_backup_platform(hass, domain=DOMAIN, platform=local_backup_platform)
    await manager.load_platforms()

    local_agent = manager.backup_agents[LOCAL_AGENT_ID]
    local_agent._loaded_backups = True

    with pytest.raises(HomeAssistantError, match="Backup abc123 not found"):
        await manager.async_restore_backup(
            TEST_LOCAL_BACKUP.slug, agent_id=LOCAL_AGENT_ID, password=None
        )
