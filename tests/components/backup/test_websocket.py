"""Tests for the Backup integration."""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup import AgentBackup, BackupAgentError, Folder
from homeassistant.components.backup.agent import BackupAgentUnreachableError
from homeassistant.components.backup.const import DATA_MANAGER, DOMAIN
from homeassistant.components.backup.manager import BackupEvent, NewBackup
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import (
    LOCAL_AGENT_ID,
    TEST_BACKUP_ABC123,
    TEST_BACKUP_DEF456,
    BackupAgentTest,
    setup_backup_integration,
)

from tests.common import async_fire_time_changed, async_mock_service
from tests.typing import WebSocketGenerator

BACKUP_CALL = call(
    agent_ids=["test-agent"],
    include_addons=["test-addon"],
    include_all_addons=False,
    include_database=True,
    include_folders=["media"],
    include_homeassistant=True,
    name="test-name",
    password="test-password",
)


@pytest.fixture
def sync_access_token_proxy(
    access_token_fixture_name: str,
    request: pytest.FixtureRequest,
) -> str:
    """Non-async proxy for the *_access_token fixture.

    Workaround for https://github.com/pytest-dev/pytest-asyncio/issues/112
    """
    return request.getfixturevalue(access_token_fixture_name)


@pytest.fixture(autouse=True)
def mock_delay_save() -> Generator[None]:
    """Mock the delay save constant."""
    with patch("homeassistant.components.backup.config.STORE_DELAY_SAVE", 0):
        yield


@pytest.fixture(name="create_backup")
def mock_create_backup() -> Generator[AsyncMock]:
    """Mock manager create backup."""
    with patch(
        "homeassistant.components.backup.BackupManager.async_create_backup"
    ) as mock_create_backup:
        yield mock_create_backup


@pytest.fixture(name="delete_backup")
def mock_delete_backup() -> Generator[AsyncMock]:
    """Mock manager delete backup."""
    with patch(
        "homeassistant.components.backup.BackupManager.async_delete_backup"
    ) as mock_delete_backup:
        yield mock_delete_backup


@pytest.fixture(name="get_backups")
def mock_get_backups() -> Generator[AsyncMock]:
    """Mock manager get backups."""
    with patch(
        "homeassistant.components.backup.BackupManager.async_get_backups"
    ) as mock_get_backups:
        yield mock_get_backups


@pytest.mark.parametrize(
    ("remote_agents", "remote_backups"),
    [
        ([], {}),
        (["remote"], {}),
        (["remote"], {"test.remote": [TEST_BACKUP_ABC123]}),
        (["remote"], {"test.remote": [TEST_BACKUP_DEF456]}),
    ],
)
async def test_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    remote_agents: list[str],
    remote_backups: dict[str, list[AgentBackup]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup info."""
    await setup_backup_integration(
        hass,
        with_hassio=False,
        backups={LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]} | remote_backups,
        remote_agents=remote_agents,
    )

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/info"})
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "side_effect", [HomeAssistantError("Boom!"), BackupAgentUnreachableError]
)
async def test_info_with_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    side_effect: Exception,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup info with one unavailable agent."""
    await setup_backup_integration(
        hass, with_hassio=False, backups={LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]}
    )
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch.object(BackupAgentTest, "async_list_backups", side_effect=side_effect):
        await client.send_json_auto_id({"type": "backup/info"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    ("remote_agents", "backups"),
    [
        ([], {}),
        (["remote"], {LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]}),
        (["remote"], {"test.remote": [TEST_BACKUP_ABC123]}),
        (["remote"], {"test.remote": [TEST_BACKUP_DEF456]}),
        (
            ["remote"],
            {
                LOCAL_AGENT_ID: [TEST_BACKUP_ABC123],
                "test.remote": [TEST_BACKUP_ABC123],
            },
        ),
    ],
)
async def test_details(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    remote_agents: list[str],
    backups: dict[str, AgentBackup],
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup info."""
    await setup_backup_integration(
        hass, with_hassio=False, backups=backups, remote_agents=remote_agents
    )

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch("pathlib.Path.exists", return_value=True):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": "abc123"}
        )
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "side_effect", [HomeAssistantError("Boom!"), BackupAgentUnreachableError]
)
async def test_details_with_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    side_effect: Exception,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup info with one unavailable agent."""
    await setup_backup_integration(
        hass, with_hassio=False, backups={LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]}
    )
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch.object(BackupAgentTest, "async_get_backup", side_effect=side_effect),
    ):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": "abc123"}
        )
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    ("remote_agents", "backups"),
    [
        ([], {}),
        (["remote"], {LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]}),
        (["remote"], {"test.remote": [TEST_BACKUP_ABC123]}),
        (["remote"], {"test.remote": [TEST_BACKUP_DEF456]}),
        (
            ["remote"],
            {
                LOCAL_AGENT_ID: [TEST_BACKUP_ABC123],
                "test.remote": [TEST_BACKUP_ABC123],
            },
        ),
    ],
)
async def test_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    remote_agents: list[str],
    backups: dict[str, AgentBackup],
    snapshot: SnapshotAssertion,
) -> None:
    """Test deleting a backup file."""
    await setup_backup_integration(
        hass, with_hassio=False, backups=backups, remote_agents=remote_agents
    )

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/info"})
    assert await client.receive_json() == snapshot

    await client.send_json_auto_id({"type": "backup/delete", "backup_id": "abc123"})
    assert await client.receive_json() == snapshot

    await client.send_json_auto_id({"type": "backup/info"})
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "side_effect", [HomeAssistantError("Boom!"), BackupAgentUnreachableError]
)
async def test_delete_with_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    side_effect: Exception,
    snapshot: SnapshotAssertion,
) -> None:
    """Test deleting a backup with one unavailable agent."""
    await setup_backup_integration(
        hass, with_hassio=False, backups={LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]}
    )
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch.object(BackupAgentTest, "async_delete_backup", side_effect=side_effect):
        await client.send_json_auto_id({"type": "backup/delete", "backup_id": "abc123"})
        assert await client.receive_json() == snapshot


async def test_agent_delete_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test deleting a backup file with a mock agent."""
    await setup_backup_integration(hass)
    hass.data[DATA_MANAGER].backup_agents = {"domain.test": BackupAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch.object(BackupAgentTest, "async_delete_backup") as delete_mock:
        await client.send_json_auto_id(
            {
                "type": "backup/delete",
                "backup_id": "abc123",
            }
        )
        assert await client.receive_json() == snapshot

    assert delete_mock.call_args == call("abc123")


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"password": "abc123"},
    ],
)
@pytest.mark.usefixtures("mock_backup_generation")
async def test_generate(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    data: dict[str, Any] | None,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating a backup."""
    await setup_backup_integration(hass, with_hassio=False)

    client = await hass_ws_client(hass)
    freezer.move_to("2024-11-13 12:01:00+01:00")
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    assert await client.receive_json() == snapshot
    await client.send_json_auto_id(
        {"type": "backup/generate", **{"agent_ids": ["backup.local"]} | (data or {})}
    )
    for _ in range(2):
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    ("parameters", "expected_error"),
    [
        (
            {"include_homeassistant": False},
            "Home Assistant must be included in backup",
        ),
        (
            {"include_addons": ["blah"]},
            "Addons and folders are not supported by core backup",
        ),
        (
            {"include_all_addons": True},
            "Addons and folders are not supported by core backup",
        ),
        (
            {"include_folders": ["ssl"]},
            "Addons and folders are not supported by core backup",
        ),
    ],
)
async def test_generate_wrong_parameters(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    parameters: dict[str, Any],
    expected_error: str,
) -> None:
    """Test generating a backup."""
    await setup_backup_integration(hass, with_hassio=False)

    client = await hass_ws_client(hass)

    default_parameters = {"type": "backup/generate", "agent_ids": ["backup.local"]}

    await client.send_json_auto_id(default_parameters | parameters)
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": expected_error,
    }


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    ("params", "expected_extra_call_params"),
    [
        ({"agent_ids": ["backup.local"]}, {"agent_ids": ["backup.local"]}),
        (
            {
                "agent_ids": ["backup.local"],
                "include_addons": ["ssl"],
                "include_database": False,
                "include_folders": ["media"],
                "name": "abc123",
            },
            {
                "agent_ids": ["backup.local"],
                "include_addons": ["ssl"],
                "include_database": False,
                "include_folders": [Folder.MEDIA],
                "name": "abc123",
            },
        ),
    ],
)
async def test_generate_calls_create(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    params: dict[str, Any],
    expected_extra_call_params: dict[str, Any],
) -> None:
    """Test translation of WS parameter to backup/generate to async_create_backup."""
    await setup_backup_integration(hass, with_hassio=False)

    client = await hass_ws_client(hass)
    freezer.move_to("2024-11-13 12:01:00+01:00")
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
        return_value=NewBackup(backup_job_id="abc123"),
    ) as generate_backup:
        await client.send_json_auto_id({"type": "backup/generate"} | params)
        result = await client.receive_json()
        assert result["success"]
        assert result["result"] == {"backup_job_id": "abc123"}
        generate_backup.assert_called_once_with(
            **{
                "include_all_addons": False,
                "include_homeassistant": True,
                "include_addons": None,
                "include_database": True,
                "include_folders": None,
                "name": None,
                "password": None,
            }
            | expected_extra_call_params
        )


@pytest.mark.parametrize(
    "backups",
    [
        {},
        {LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]},
    ],
)
async def test_restore_local_agent(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backups: dict[str, AgentBackup],
    snapshot: SnapshotAssertion,
) -> None:
    """Test calling the restore command."""
    await setup_backup_integration(hass, with_hassio=False, backups=backups)
    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.write_text"),
    ):
        await client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": "abc123",
                "agent_id": "backup.local",
            }
        )
        assert await client.receive_json() == snapshot
    assert len(restart_calls) == snapshot


@pytest.mark.parametrize(
    ("remote_agents", "backups"),
    [
        (["remote"], {}),
        (["remote"], {"test.remote": [TEST_BACKUP_ABC123]}),
    ],
)
async def test_restore_remote_agent(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    remote_agents: list[str],
    backups: dict[str, AgentBackup],
    snapshot: SnapshotAssertion,
) -> None:
    """Test calling the restore command."""
    await setup_backup_integration(
        hass, with_hassio=False, backups=backups, remote_agents=remote_agents
    )
    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch("pathlib.Path.write_text"):
        await client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": "abc123",
                "agent_id": "test.remote",
            }
        )
        assert await client.receive_json() == snapshot
    assert len(restart_calls) == snapshot


@pytest.mark.parametrize(
    "access_token_fixture_name",
    ["hass_access_token", "hass_supervisor_access_token"],
)
@pytest.mark.parametrize(
    ("with_hassio"),
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
@pytest.mark.usefixtures("supervisor_client")
async def test_backup_end(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    sync_access_token_proxy: str,
    *,
    access_token_fixture_name: str,
    with_hassio: bool,
) -> None:
    """Test handling of post backup actions from a WS command."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass, sync_access_token_proxy)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_post_backup_actions",
    ):
        await client.send_json_auto_id({"type": "backup/end"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "access_token_fixture_name",
    ["hass_access_token", "hass_supervisor_access_token"],
)
@pytest.mark.parametrize(
    ("with_hassio"),
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
@pytest.mark.usefixtures("supervisor_client")
async def test_backup_start(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    sync_access_token_proxy: str,
    *,
    access_token_fixture_name: str,
    with_hassio: bool,
) -> None:
    """Test handling of pre backup actions from a WS command."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass, sync_access_token_proxy)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_pre_backup_actions",
    ):
        await client.send_json_auto_id({"type": "backup/start"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError(),
        HomeAssistantError("Boom"),
        Exception("Boom"),
    ],
)
@pytest.mark.usefixtures("supervisor_client")
async def test_backup_end_exception(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    hass_supervisor_access_token: str,
    exception: Exception,
) -> None:
    """Test exception handling while running post backup actions from a WS command."""
    await setup_backup_integration(hass, with_hassio=True)

    client = await hass_ws_client(hass, hass_supervisor_access_token)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_post_backup_actions",
        side_effect=exception,
    ):
        await client.send_json_auto_id({"type": "backup/end"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError(),
        HomeAssistantError("Boom"),
        Exception("Boom"),
    ],
)
@pytest.mark.usefixtures("supervisor_client")
async def test_backup_start_exception(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    hass_supervisor_access_token: str,
    exception: Exception,
) -> None:
    """Test exception handling while running pre backup actions from a WS command."""
    await setup_backup_integration(hass, with_hassio=True)

    client = await hass_ws_client(hass, hass_supervisor_access_token)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_pre_backup_actions",
        side_effect=exception,
    ):
        await client.send_json_auto_id({"type": "backup/start"})
        assert await client.receive_json() == snapshot


async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup agents info."""
    await setup_backup_integration(hass, with_hassio=False)
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    assert await client.receive_json() == snapshot


async def test_agents_download(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test WS command to start downloading a backup."""
    await setup_backup_integration(hass, with_hassio=False)
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "agent_id": "domain.test",
            "backup_id": "abc123",
        }
    )
    with patch.object(BackupAgentTest, "async_download_backup") as download_mock:
        assert await client.receive_json() == snapshot
        assert download_mock.call_args[0] == ("abc123",)
        assert download_mock.call_args[1] == {
            "path": Path(hass.config.path("tmp_backups"), "abc123.tar"),
        }


async def test_agents_download_exception(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test WS command to start downloading a backup throwing an exception."""
    await setup_backup_integration(hass)
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "agent_id": "domain.test",
            "backup_id": "abc123",
        }
    )
    with patch.object(BackupAgentTest, "async_download_backup") as download_mock:
        download_mock.side_effect = Exception("Boom")
        assert await client.receive_json() == snapshot


async def test_agents_download_unknown_agent(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test downloading a backup with an unknown agent."""
    await setup_backup_integration(hass)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "agent_id": "domain.test",
            "backup_id": "abc123",
        }
    )
    assert await client.receive_json() == snapshot


@pytest.mark.usefixtures("create_backup", "delete_backup", "get_backups")
@pytest.mark.parametrize(
    "storage_data",
    [
        {},
        {
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": ["test-addon"],
                "include_all_addons": True,
                "include_database": True,
                "include_folders": ["media"],
                "name": "test-name",
                "password": "test-password",
            },
            "delete_after": {"copies": 3, "days": 7},
            "last_automatic_backup": datetime.fromisoformat(
                "2024-10-26T04:45:00+01:00"
            ),
            "schedule": "daily",
        },
        {
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": False,
                "include_folders": None,
                "name": None,
                "password": None,
            },
            "delete_after": {"copies": 3, "days": None},
            "last_automatic_backup": None,
            "schedule": "never",
        },
        {
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": False,
                "include_folders": None,
                "name": None,
                "password": None,
            },
            "delete_after": {"copies": None, "days": 7},
            "last_automatic_backup": datetime.fromisoformat(
                "2024-10-26T04:45:00+01:00"
            ),
            "schedule": "never",
        },
        {
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": False,
                "include_folders": None,
                "name": None,
                "password": None,
            },
            "delete_after": {"copies": None, "days": None},
            "last_automatic_backup": None,
            "schedule": "mon",
        },
        {
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": False,
                "include_folders": None,
                "name": None,
                "password": None,
            },
            "delete_after": {"copies": None, "days": None},
            "last_automatic_backup": None,
            "schedule": "sat",
        },
    ],
)
async def test_config_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    hass_storage: dict[str, Any],
    storage_data: dict[str, Any],
) -> None:
    """Test getting backup config info."""
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": 1,
    }

    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot


@pytest.mark.usefixtures("create_backup", "delete_backup", "get_backups")
@pytest.mark.parametrize(
    "command",
    [
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "delete_after": {"copies": None, "days": 7},
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "schedule": "daily",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "schedule": "mon",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "schedule": "never",
        },
        {
            "type": "backup/config/update",
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": ["test-addon"],
                "include_folders": ["media"],
                "name": "test-name",
                "password": "test-password",
            },
            "schedule": "daily",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "delete_after": {"copies": 3, "days": 7},
            "schedule": "daily",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "delete_after": {"copies": None, "days": None},
            "schedule": "daily",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "delete_after": {"copies": 3, "days": None},
            "schedule": "daily",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "delete_after": {"copies": None, "days": 7},
            "schedule": "daily",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "delete_after": {"copies": 3},
            "schedule": "daily",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "delete_after": {"days": 7},
            "schedule": "daily",
        },
    ],
)
async def test_config_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    command: dict[str, Any],
    hass_storage: dict[str, Any],
) -> None:
    """Test updating the backup config."""
    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot

    await client.send_json_auto_id(command)
    result = await client.receive_json()

    assert result["success"]

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot
    await hass.async_block_till_done()

    assert hass_storage[DOMAIN] == snapshot


@pytest.mark.usefixtures("create_backup", "delete_backup", "get_backups")
@pytest.mark.parametrize(
    "command",
    [
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "schedule": "someday",
        },
    ],
)
async def test_config_update_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    command: dict[str, Any],
) -> None:
    """Test errors when updating the backup config."""
    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot

    await client.send_json_auto_id(command)
    result = await client.receive_json()

    assert not result["success"]

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    (
        "command",
        "last_automatic_backup",
        "move_to_time",
        "backup_time",
        "backup_calls",
        "call_args",
    ),
    [
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": "daily",
            },
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            BACKUP_CALL,
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": "mon",
            },
            "2024-11-11T04:45:00+01:00",
            "2024-11-18T04:45:00+01:00",
            "2024-11-18T04:45:00+01:00",
            1,
            BACKUP_CALL,
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": "never",
            },
            "2024-11-11T04:45:00+01:00",
            "2034-11-11T12:00:00+01:00",  # ten years later and still no backups
            "2024-11-11T04:45:00+01:00",
            0,
            None,
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": "daily",
            },
            "2024-10-26T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            BACKUP_CALL,
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": "mon",
            },
            "2024-10-26T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",  # missed event uses daily schedule once
            1,
            BACKUP_CALL,
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": "never",
            },
            "2024-10-26T04:45:00+01:00",
            "2034-11-11T12:00:00+01:00",  # ten years later and still no backups
            "2024-10-26T04:45:00+01:00",
            0,
            None,
        ),
    ],
)
async def test_config_schedule_logic(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    create_backup: AsyncMock,
    command: dict[str, Any],
    last_automatic_backup: str,
    move_to_time: str,
    backup_time: str,
    backup_calls: int,
    call_args: Any,
) -> None:
    """Test config schedule logic."""
    client = await hass_ws_client(hass)
    storage_data = {
        "create_backup": {
            "agent_ids": ["test-agent"],
            "include_addons": ["test-addon"],
            "include_all_addons": False,
            "include_database": True,
            "include_folders": ["media"],
            "name": "test-name",
            "password": "test-password",
        },
        "delete_after": {"copies": None, "days": None},
        "last_automatic_backup": datetime.fromisoformat(last_automatic_backup),
        "schedule": "daily",
    }
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": 1,
    }
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-11 12:00:00+01:00")

    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(command)
    result = await client.receive_json()

    assert result["success"]

    freezer.move_to(move_to_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert create_backup.call_count == backup_calls
    assert create_backup.call_args == call_args
    async_fire_time_changed(hass, fire_all=True)  # flush out storage save
    await hass.async_block_till_done()
    assert hass_storage[DOMAIN]["data"]["last_automatic_backup"] == backup_time


@pytest.mark.parametrize(
    (
        "command",
        "backups",
        "get_backups_agent_errors",
        "delete_backup_agent_errors",
        "last_backup_time",
        "next_time",
        "backup_time",
        "backup_calls",
        "get_backups_calls",
        "delete_calls",
        "delete_args_list",
    ),
    [
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": None, "days": None},
                "schedule": "daily",
            },
            {
                "backup-1": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-11T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-12T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,  # we get backups even if delete after copies is None
            0,
            [],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": 3, "days": None},
                "schedule": "daily",
            },
            {
                "backup-1": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-11T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-12T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            0,
            [],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": 3, "days": None},
                "schedule": "daily",
            },
            {
                "backup-1": MagicMock(date="2024-11-09T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-11T04:45:00+01:00"),
                "backup-4": MagicMock(date="2024-11-12T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            1,
            [call("backup-1")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": 2, "days": None},
                "schedule": "daily",
            },
            {
                "backup-1": MagicMock(date="2024-11-09T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-11T04:45:00+01:00"),
                "backup-4": MagicMock(date="2024-11-12T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            2,
            [call("backup-1"), call("backup-2")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": 2, "days": None},
                "schedule": "daily",
            },
            {
                "backup-1": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-11T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-12T04:45:00+01:00"),
            },
            {"test-agent": BackupAgentError("Boom!")},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            1,
            [call("backup-1")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": 2, "days": None},
                "schedule": "daily",
            },
            {
                "backup-1": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-11T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-12T04:45:00+01:00"),
            },
            {},
            {"test-agent": BackupAgentError("Boom!")},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            1,
            [call("backup-1")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": 0, "days": None},
                "schedule": "daily",
            },
            {
                "backup-1": MagicMock(date="2024-11-09T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-11T04:45:00+01:00"),
                "backup-4": MagicMock(date="2024-11-12T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            3,
            [call("backup-1"), call("backup-2"), call("backup-3")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": 0, "days": None},
                "schedule": "daily",
            },
            {
                "backup-1": MagicMock(date="2024-11-12T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            0,
            [],
        ),
    ],
)
async def test_config_delete_after_copies_logic(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    create_backup: AsyncMock,
    delete_backup: AsyncMock,
    get_backups: AsyncMock,
    command: dict[str, Any],
    backups: dict[str, Any],
    get_backups_agent_errors: dict[str, Exception],
    delete_backup_agent_errors: dict[str, Exception],
    last_backup_time: str,
    next_time: str,
    backup_time: str,
    backup_calls: int,
    get_backups_calls: int,
    delete_calls: int,
    delete_args_list: Any,
) -> None:
    """Test config delete after copies logic."""
    client = await hass_ws_client(hass)
    storage_data = {
        "create_backup": {
            "agent_ids": ["test-agent"],
            "include_addons": ["test-addon"],
            "include_all_addons": False,
            "include_database": True,
            "include_folders": ["media"],
            "name": "test-name",
            "password": "test-password",
        },
        "delete_after": {"copies": None, "days": None},
        "last_automatic_backup": datetime.fromisoformat(last_backup_time),
        "schedule": "daily",
    }
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": 1,
    }
    get_backups.return_value = (backups, get_backups_agent_errors)
    delete_backup.return_value = delete_backup_agent_errors
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-11 12:00:00+01:00")

    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(command)
    result = await client.receive_json()

    assert result["success"]

    freezer.move_to(next_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert create_backup.call_count == backup_calls
    assert get_backups.call_count == get_backups_calls
    assert delete_backup.call_count == delete_calls
    assert delete_backup.call_args_list == delete_args_list
    async_fire_time_changed(hass, fire_all=True)  # flush out storage save
    await hass.async_block_till_done()
    assert hass_storage[DOMAIN]["data"]["last_automatic_backup"] == backup_time


@pytest.mark.parametrize(
    (
        "command",
        "backups",
        "get_backups_agent_errors",
        "delete_backup_agent_errors",
        "last_backup_time",
        "start_time",
        "next_time",
        "get_backups_calls",
        "delete_calls",
        "delete_args_list",
    ),
    [
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": None, "days": 2},
                "schedule": "never",
            },
            {
                "backup-1": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-11T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            1,
            [call("backup-1")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": None, "days": 3},
                "schedule": "never",
            },
            {
                "backup-1": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-11T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            0,
            [],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": None, "days": 2},
                "schedule": "never",
            },
            {
                "backup-1": MagicMock(date="2024-11-09T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-11T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            2,
            [call("backup-1"), call("backup-2")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": None, "days": 2},
                "schedule": "never",
            },
            {
                "backup-1": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-11T04:45:00+01:00"),
            },
            {"test-agent": BackupAgentError("Boom!")},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            1,
            [call("backup-1")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": None, "days": 2},
                "schedule": "never",
            },
            {
                "backup-1": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-11T04:45:00+01:00"),
            },
            {},
            {"test-agent": BackupAgentError("Boom!")},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            1,
            [call("backup-1")],
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "delete_after": {"copies": None, "days": 0},
                "schedule": "never",
            },
            {
                "backup-1": MagicMock(date="2024-11-09T04:45:00+01:00"),
                "backup-2": MagicMock(date="2024-11-10T04:45:00+01:00"),
                "backup-3": MagicMock(date="2024-11-11T04:45:00+01:00"),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            2,
            [call("backup-1"), call("backup-2")],
        ),
    ],
)
async def test_config_delete_after_days_logic(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    delete_backup: AsyncMock,
    get_backups: AsyncMock,
    command: dict[str, Any],
    backups: dict[str, Any],
    get_backups_agent_errors: dict[str, Exception],
    delete_backup_agent_errors: dict[str, Exception],
    last_backup_time: str,
    start_time: str,
    next_time: str,
    get_backups_calls: int,
    delete_calls: int,
    delete_args_list: list[Any],
) -> None:
    """Test config delete after logic."""
    client = await hass_ws_client(hass)
    storage_data = {
        "create_backup": {
            "agent_ids": ["test-agent"],
            "include_addons": ["test-addon"],
            "include_all_addons": False,
            "include_database": True,
            "include_folders": ["media"],
            "name": "test-name",
            "password": "test-password",
        },
        "delete_after": {"copies": None, "days": None},
        "last_automatic_backup": datetime.fromisoformat(last_backup_time),
        "schedule": "never",
    }
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": 1,
    }
    get_backups.return_value = (backups, get_backups_agent_errors)
    delete_backup.return_value = delete_backup_agent_errors
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(start_time)

    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(command)
    result = await client.receive_json()

    assert result["success"]

    freezer.move_to(next_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert get_backups.call_count == get_backups_calls
    assert delete_backup.call_count == delete_calls
    assert delete_backup.call_args_list == delete_args_list
    async_fire_time_changed(hass, fire_all=True)  # flush out storage save
    await hass.async_block_till_done()


async def test_subscribe_event(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating a backup."""
    await setup_backup_integration(hass, with_hassio=False)

    manager = hass.data[DATA_MANAGER]
    manager.backup_event = BackupEvent(event_type="test")

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    assert await client.receive_json() == snapshot
    assert await client.receive_json() == snapshot

    manager.async_on_backup_event(BackupEvent(event_type="test2"))
    assert await client.receive_json() == snapshot
