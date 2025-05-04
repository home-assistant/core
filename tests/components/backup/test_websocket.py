"""Tests for the Backup integration."""

from collections.abc import Generator
from dataclasses import replace
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup import (
    AddonInfo,
    AgentBackup,
    BackupAgentError,
    BackupNotFound,
    BackupReaderWriterError,
    Folder,
    store,
)
from homeassistant.components.backup.agent import BackupAgentUnreachableError
from homeassistant.components.backup.const import DATA_MANAGER, DOMAIN
from homeassistant.components.backup.manager import (
    AgentBackupStatus,
    CreateBackupEvent,
    CreateBackupState,
    ManagerBackup,
    NewBackup,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.setup import async_setup_component

from .common import (
    LOCAL_AGENT_ID,
    TEST_BACKUP_ABC123,
    TEST_BACKUP_DEF456,
    mock_backup_agent,
    setup_backup_integration,
    setup_backup_platform,
)

from tests.common import async_fire_time_changed, async_mock_service
from tests.typing import WebSocketGenerator

BACKUP_CALL = call(
    agent_ids=["test.test-agent"],
    backup_name="test-name",
    extra_metadata={"instance_id": ANY, "with_automatic_settings": True},
    include_addons=[],
    include_all_addons=False,
    include_database=True,
    include_folders=None,
    include_homeassistant=True,
    password="test-password",
    on_progress=ANY,
)

DEFAULT_STORAGE_DATA: dict[str, Any] = {
    "backups": [],
    "config": {
        "agents": {},
        "automatic_backups_configured": False,
        "create_backup": {
            "agent_ids": [],
            "include_addons": None,
            "include_all_addons": False,
            "include_database": True,
            "include_folders": None,
            "name": None,
            "password": None,
        },
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
        "retention": {
            "copies": None,
            "days": None,
        },
        "schedule": {"days": [], "recurrence": "never", "state": "never", "time": None},
    },
}
DAILY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

TEST_MANAGER_BACKUP = ManagerBackup(
    addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
    agents={"test.test-agent": AgentBackupStatus(protected=True, size=0)},
    backup_id="backup-1",
    date="1970-01-01T00:00:00.000Z",
    database_included=True,
    extra_metadata={"instance_id": "abc123", "with_automatic_settings": True},
    folders=[Folder.MEDIA, Folder.SHARE],
    homeassistant_included=True,
    homeassistant_version="2024.12.0",
    name="Test",
    failed_agent_ids=[],
    with_automatic_settings=True,
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
    with patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0):
        yield


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
        (["test.remote"], {}),
        (["test.remote"], {"test.remote": [TEST_BACKUP_ABC123]}),
        (["test.remote"], {"test.remote": [TEST_BACKUP_DEF456]}),
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
    "side_effect",
    [Exception("Oops"), HomeAssistantError("Boom!"), BackupAgentUnreachableError],
)
async def test_info_with_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    side_effect: Exception,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup info with one unavailable agent."""
    mock_agents = await setup_backup_integration(
        hass,
        with_hassio=False,
        backups={LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]},
        remote_agents=["test.remote"],
    )
    mock_agents["test.remote"].async_list_backups.side_effect = side_effect

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/info"})
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    ("remote_agents", "backups"),
    [
        ([], {}),
        (["test.remote"], {LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]}),
        (["test.remote"], {"test.remote": [TEST_BACKUP_ABC123]}),
        (["test.remote"], {"test.remote": [TEST_BACKUP_DEF456]}),
        (
            ["test.remote"],
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
    backups: dict[str, list[AgentBackup]],
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
    "side_effect",
    [Exception("Oops"), HomeAssistantError("Boom!"), BackupAgentUnreachableError],
)
async def test_details_with_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    side_effect: Exception,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup info with one unavailable agent."""
    mock_agents = await setup_backup_integration(
        hass,
        with_hassio=False,
        backups={LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]},
        remote_agents=["test.remote"],
    )
    mock_agents["test.remote"].async_get_backup.side_effect = side_effect

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch("pathlib.Path.exists", return_value=True):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": "abc123"}
        )
        assert await client.receive_json() == snapshot


async def test_details_get_backup_returns_none(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup info when the agent returns None from get_backup."""
    mock_agents = await setup_backup_integration(hass, remote_agents=["test.remote"])
    mock_agents["test.remote"].async_get_backup.return_value = None
    mock_agents["test.remote"].async_get_backup.side_effect = None

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch("pathlib.Path.exists", return_value=True):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": "abc123"}
        )
        assert await client.receive_json() == snapshot
    assert (
        "Detected that integration 'test' returns None from BackupAgent.async_get_backup."
        in caplog.text
    )


@pytest.mark.parametrize(
    ("remote_agents", "backups"),
    [
        ([], {}),
        (["test.remote"], {LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]}),
        (["test.remote"], {"test.remote": [TEST_BACKUP_ABC123]}),
        (["test.remote"], {"test.remote": [TEST_BACKUP_DEF456]}),
        (
            ["test.remote"],
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
    backups: dict[str, list[AgentBackup]],
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
    "storage_data",
    [
        DEFAULT_STORAGE_DATA,
        DEFAULT_STORAGE_DATA
        | {
            "backups": [
                {
                    "backup_id": "abc123",
                    "failed_agent_ids": ["test.remote"],
                }
            ]
        },
    ],
)
@pytest.mark.parametrize(
    "side_effect", [None, HomeAssistantError("Boom!"), BackupAgentUnreachableError]
)
async def test_delete_with_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    side_effect: Exception,
    storage_data: dict[str, Any] | None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test deleting a backup with one unavailable agent."""
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": store.STORAGE_VERSION,
        "minor_version": store.STORAGE_VERSION_MINOR,
    }
    mock_agents = await setup_backup_integration(
        hass,
        with_hassio=False,
        backups={
            LOCAL_AGENT_ID: [TEST_BACKUP_ABC123],
            "test.remote": [TEST_BACKUP_ABC123],
        },
        remote_agents=["test.remote"],
    )
    mock_agents["test.remote"].async_delete_backup.side_effect = side_effect

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/delete", "backup_id": "abc123"})
    assert await client.receive_json() == snapshot

    await client.send_json_auto_id({"type": "backup/info"})
    assert await client.receive_json() == snapshot


async def test_agent_delete_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test deleting a backup file with a mock agent."""
    mock_agents = await setup_backup_integration(
        hass, with_hassio=False, remote_agents=["test.remote"]
    )

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": "abc123",
        }
    )
    assert await client.receive_json() == snapshot

    assert mock_agents["test.remote"].async_delete_backup.call_args == call("abc123")


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
    for _ in range(6):
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
                "include_database": False,
                "name": "abc123",
            },
            {
                "agent_ids": ["backup.local"],
                "include_addons": None,
                "include_database": False,
                "include_folders": None,
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
    """Test translation of WS parameter to backup/generate to async_initiate_backup."""
    await setup_backup_integration(hass, with_hassio=False)

    client = await hass_ws_client(hass)
    freezer.move_to("2024-11-13 12:01:00+01:00")
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_initiate_backup",
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
    (
        "create_backup_settings",
        "expected_call_params",
        "side_effect",
        "last_completed_automatic_backup",
    ),
    [
        (
            {
                "agent_ids": ["test.remote"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "name": None,
                "password": None,
            },
            {
                "agent_ids": ["test.remote"],
                "backup_name": ANY,
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
            None,
            "2024-11-13T12:01:01+01:00",
        ),
        (
            {
                "agent_ids": ["test.remote"],
                "include_addons": ["test-addon"],
                "include_all_addons": False,
                "include_database": True,
                "include_folders": ["media"],
                "name": "test-name",
                "password": "test-password",
            },
            {
                "agent_ids": ["test.remote"],
                "backup_name": "test-name",
                "extra_metadata": {
                    "instance_id": ANY,
                    "with_automatic_settings": True,
                },
                "include_addons": ["test-addon"],
                "include_all_addons": False,
                "include_database": True,
                "include_folders": [Folder.MEDIA],
                "include_homeassistant": True,
                "on_progress": ANY,
                "password": "test-password",
            },
            None,
            "2024-11-13T12:01:01+01:00",
        ),
        (
            {
                "agent_ids": ["test.remote"],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "name": None,
                "password": None,
            },
            {
                "agent_ids": ["test.remote"],
                "backup_name": ANY,
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
            BackupAgentError("Boom!"),
            None,
        ),
    ],
)
async def test_generate_with_default_settings_calls_create(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    create_backup: AsyncMock,
    create_backup_settings: dict[str, Any],
    expected_call_params: dict[str, Any],
    side_effect: Exception | None,
    last_completed_automatic_backup: str,
) -> None:
    """Test backup/generate_with_automatic_settings calls async_initiate_backup."""
    created_backup: MagicMock = create_backup.return_value[1].result().backup
    created_backup.protected = create_backup_settings["password"] is not None
    client = await hass_ws_client(hass)
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-13T12:01:00+01:00")
    mock_agents = await setup_backup_integration(
        hass, with_hassio=False, remote_agents=["test.remote"]
    )

    await client.send_json_auto_id(
        {"type": "backup/config/update", "create_backup": create_backup_settings}
    )
    result = await client.receive_json()
    assert result["success"]

    freezer.tick()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass_storage[DOMAIN]["data"]["config"]["create_backup"]
        == create_backup_settings
    )
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_attempted_automatic_backup"]
        is None
    )
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_completed_automatic_backup"]
        is None
    )

    mock_agents["test.remote"].async_upload_backup.side_effect = side_effect
    await client.send_json_auto_id({"type": "backup/generate_with_automatic_settings"})
    result = await client.receive_json()
    assert result["success"]
    assert result["result"] == {"backup_job_id": "abc123"}

    await hass.async_block_till_done()

    create_backup.assert_called_once_with(**expected_call_params)

    freezer.tick()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_attempted_automatic_backup"]
        == "2024-11-13T12:01:01+01:00"
    )
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_completed_automatic_backup"]
        == last_completed_automatic_backup
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
    backups: dict[str, list[AgentBackup]],
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
        patch("homeassistant.components.backup.manager.validate_password"),
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
        (["test.remote"], {}),
        (["test.remote"], {"test.remote": [TEST_BACKUP_ABC123]}),
    ],
)
async def test_restore_remote_agent(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    remote_agents: list[str],
    backups: dict[str, list[AgentBackup]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test calling the restore command."""

    await setup_backup_integration(
        hass, with_hassio=False, backups=backups, remote_agents=remote_agents
    )
    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with (
        patch("pathlib.Path.write_text"),
        patch("pathlib.Path.open"),
        patch("homeassistant.components.backup.manager.validate_password"),
    ):
        await client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": "abc123",
                "agent_id": "test.remote",
            }
        )
        assert await client.receive_json() == snapshot
    assert len(restart_calls) == snapshot


async def test_restore_remote_agent_get_backup_returns_none(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test calling the restore command when the agent returns None from get_backup."""
    mock_agents = await setup_backup_integration(hass, remote_agents=["test.remote"])
    mock_agents["test.remote"].async_get_backup.return_value = None
    mock_agents["test.remote"].async_get_backup.side_effect = None
    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/restore",
            "backup_id": "abc123",
            "agent_id": "test.remote",
        }
    )
    assert await client.receive_json() == snapshot
    assert len(restart_calls) == 0
    assert (
        "Detected that integration 'test' returns None from BackupAgent.async_get_backup."
        in caplog.text
    )


async def test_restore_wrong_password(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test calling the restore command."""
    await setup_backup_integration(
        hass, with_hassio=False, backups={LOCAL_AGENT_ID: [TEST_BACKUP_ABC123]}
    )
    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.write_text"),
        patch(
            "homeassistant.components.backup.manager.validate_password",
            return_value=False,
        ),
    ):
        await client.send_json_auto_id(
            {
                "type": "backup/restore",
                "backup_id": "abc123",
                "agent_id": "backup.local",
            }
        )
        assert await client.receive_json() == snapshot
    assert len(restart_calls) == 0


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
    await setup_backup_integration(
        hass, with_hassio=False, remote_agents=["test.remote"]
    )

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    assert await client.receive_json() == snapshot


@pytest.mark.usefixtures("get_backups")
@pytest.mark.parametrize(
    "storage_data",
    [
        {},
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": False,
                        "create_backup": {
                            "agent_ids": ["test-agent"],
                            "include_addons": ["test-addon"],
                            "include_all_addons": True,
                            "include_database": True,
                            "include_folders": ["media"],
                            "name": "test-name",
                            "password": "test-password",
                        },
                        "retention": {"copies": 3, "days": 7},
                        "last_attempted_automatic_backup": "2024-10-26T04:45:00+01:00",
                        "last_completed_automatic_backup": "2024-10-26T04:45:00+01:00",
                        "schedule": {
                            "days": DAILY,
                            "recurrence": "custom_days",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": True,
                        "create_backup": {
                            "agent_ids": ["test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": 3, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": [],
                            "recurrence": "never",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": False,
                        "create_backup": {
                            "agent_ids": ["test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": 7},
                        "last_attempted_automatic_backup": "2024-10-27T04:45:00+01:00",
                        "last_completed_automatic_backup": "2024-10-26T04:45:00+01:00",
                        "schedule": {
                            "days": [],
                            "recurrence": "never",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": False,
                        "create_backup": {
                            "agent_ids": ["test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": ["mon"],
                            "recurrence": "custom_days",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": False,
                        "create_backup": {
                            "agent_ids": ["test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": [],
                            "recurrence": "never",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": False,
                        "create_backup": {
                            "agent_ids": ["test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": ["mon", "sun"],
                            "recurrence": "custom_days",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {
                            "test-agent1": {"protected": True, "retention": None},
                            "test-agent2": {"protected": False, "retention": None},
                        },
                        "automatic_backups_configured": False,
                        "create_backup": {
                            "agent_ids": ["test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": ["mon", "sun"],
                            "recurrence": "custom_days",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": True,
                        "create_backup": {
                            "agent_ids": ["hassio.local", "hassio.share", "test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": [],
                            "recurrence": "never",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": True,
                        "create_backup": {
                            "agent_ids": ["backup.local", "test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": [],
                            "recurrence": "never",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {
                            "test-agent1": {
                                "protected": True,
                                "retention": {"copies": 3, "days": None},
                            },
                            "test-agent2": {
                                "protected": False,
                                "retention": {"copies": None, "days": 7},
                            },
                        },
                        "automatic_backups_configured": False,
                        "create_backup": {
                            "agent_ids": ["test-agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": ["mon", "sun"],
                            "recurrence": "custom_days",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        },
    ],
)
@pytest.mark.parametrize(
    ("with_hassio"),
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
@pytest.mark.usefixtures("supervisor_client")
@patch("homeassistant.components.backup.config.random.randint", Mock(return_value=600))
async def test_config_load_config_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    hass_storage: dict[str, Any],
    with_hassio: bool,
    storage_data: dict[str, Any],
) -> None:
    """Test loading stored backup config and reading it via config/info."""
    client = await hass_ws_client(hass)
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-13T12:01:00+01:00")

    hass_storage.update(storage_data)

    await setup_backup_integration(hass, with_hassio=with_hassio)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot


@pytest.mark.usefixtures("get_backups")
@pytest.mark.parametrize(
    "commands",
    [
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "retention": {"copies": None, "days": 7},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": {"recurrence": "daily", "time": "06:00"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": {"days": ["mon"], "recurrence": "custom_days"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": {"recurrence": "never"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "schedule": {"days": ["mon", "sun"], "recurrence": "custom_days"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {
                    "agent_ids": ["test-agent"],
                    "include_addons": ["test-addon"],
                    "include_folders": ["media"],
                    "name": "test-name",
                    "password": "test-password",
                },
                "schedule": {"recurrence": "daily"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "retention": {"copies": 3, "days": 7},
                "schedule": {"recurrence": "daily"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "retention": {"copies": None, "days": None},
                "schedule": {"recurrence": "daily"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "retention": {"copies": 3, "days": None},
                "schedule": {"recurrence": "daily"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "retention": {"copies": None, "days": 7},
                "schedule": {"recurrence": "daily"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "retention": {"copies": 3},
                "schedule": {"recurrence": "daily"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test-agent"]},
                "retention": {"days": 7},
                "schedule": {"recurrence": "daily"},
            }
        ],
        [
            {
                "type": "backup/config/update",
                "agents": {
                    "test-agent1": {"protected": True},
                    "test-agent2": {"protected": False},
                },
            }
        ],
        [
            # Test we can update AgentConfig
            {
                "type": "backup/config/update",
                "agents": {
                    "test-agent1": {"protected": True},
                    "test-agent2": {"protected": False},
                },
            },
            {
                "type": "backup/config/update",
                "agents": {
                    "test-agent1": {"protected": False},
                    "test-agent2": {"protected": True},
                },
            },
            {
                "type": "backup/config/update",
                "agents": {
                    "test-agent1": {"retention": {"copies": 3}},
                    "test-agent2": {"retention": None},
                },
            },
            {
                "type": "backup/config/update",
                "agents": {
                    "test-agent1": {"retention": None},
                    "test-agent2": {"retention": {"days": 7}},
                },
            },
        ],
        [
            {
                "type": "backup/config/update",
                "automatic_backups_configured": False,
            }
        ],
        [
            {
                "type": "backup/config/update",
                "automatic_backups_configured": True,
            }
        ],
    ],
)
@patch("homeassistant.components.backup.config.random.randint", Mock(return_value=600))
async def test_config_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    commands: list[dict[str, Any]],
    hass_storage: dict[str, Any],
) -> None:
    """Test updating the backup config."""
    client = await hass_ws_client(hass)
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-13T12:01:00+01:00")

    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot

    for command in commands:
        await client.send_json_auto_id(command)
        result = await client.receive_json()
        assert result["success"]

        await client.send_json_auto_id({"type": "backup/config/info"})
        assert await client.receive_json() == snapshot
        await hass.async_block_till_done()

    # Trigger store write
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass_storage[DOMAIN] == snapshot


@pytest.mark.usefixtures("get_backups")
@pytest.mark.parametrize(
    "command",
    [
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "recurrence": "blah",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "recurrence": "never",
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "recurrence": {"state": "someday"},
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "recurrence": {"time": "early"},
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "recurrence": {"days": "mon"},
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
            "recurrence": {"days": ["fun"]},
        },
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent", "test-agent"]},
        },
        {
            "type": "backup/config/update",
            "create_backup": {"include_addons": ["my-addon", "my-addon"]},
        },
        {
            "type": "backup/config/update",
            "create_backup": {"include_folders": ["media", "media"]},
        },
        {
            "type": "backup/config/update",
            "agents": {"test-agent1": {"favorite": True}},
        },
        {
            "type": "backup/config/update",
            "retention": {"copies": 0},
        },
        {
            "type": "backup/config/update",
            "retention": {"days": 0},
        },
        {
            "type": "backup/config/update",
            "agents": {"test-agent1": {"retention": {"copies": 0}}},
        },
        {
            "type": "backup/config/update",
            "agents": {"test-agent1": {"retention": {"days": 0}}},
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
        "commands",
        "last_completed_automatic_backup",
        "time_1",
        "time_2",
        "attempted_backup_time",
        "completed_backup_time",
        "scheduled_backup_time",
        "additional_backup",
        "backup_calls_1",
        "backup_calls_2",
        "call_args",
        "create_backup_side_effect",
    ),
    [
        (
            # No config update
            [],
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            None,
        ),
        (
            # Unchanged schedule
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"recurrence": "daily"},
                }
            ],
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"days": ["mon"], "recurrence": "custom_days"},
                }
            ],
            "2024-11-11T04:45:00+01:00",
            "2024-11-18T04:55:00+01:00",
            "2024-11-25T04:55:00+01:00",
            "2024-11-18T04:55:00+01:00",
            "2024-11-18T04:55:00+01:00",
            "2024-11-18T04:55:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {
                        "days": ["mon"],
                        "recurrence": "custom_days",
                        "time": "03:45",
                    },
                }
            ],
            "2024-11-11T03:45:00+01:00",
            "2024-11-18T03:45:00+01:00",
            "2024-11-25T03:45:00+01:00",
            "2024-11-18T03:45:00+01:00",
            "2024-11-18T03:45:00+01:00",
            "2024-11-18T03:45:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"recurrence": "daily", "time": "03:45"},
                }
            ],
            "2024-11-11T03:45:00+01:00",
            "2024-11-12T03:45:00+01:00",
            "2024-11-13T03:45:00+01:00",
            "2024-11-12T03:45:00+01:00",
            "2024-11-12T03:45:00+01:00",
            "2024-11-12T03:45:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"days": ["wed", "fri"], "recurrence": "custom_days"},
                }
            ],
            "2024-11-11T04:45:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-15T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"recurrence": "never"},
                }
            ],
            "2024-11-11T04:45:00+01:00",
            "2034-11-11T12:00:00+01:00",  # ten years later and still no backups
            "2034-11-11T13:00:00+01:00",
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T04:45:00+01:00",
            None,
            False,
            0,
            0,
            None,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"days": [], "recurrence": "custom_days"},
                }
            ],
            "2024-11-11T04:45:00+01:00",
            "2034-11-11T12:00:00+01:00",  # ten years later and still no backups
            "2034-11-11T13:00:00+01:00",
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T04:45:00+01:00",
            None,
            False,
            0,
            0,
            None,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"recurrence": "daily"},
                }
            ],
            "2024-10-26T04:45:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"days": ["mon"], "recurrence": "custom_days"},
                }
            ],
            "2024-10-26T04:45:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",  # missed event uses daily schedule once
            "2024-11-12T04:55:00+01:00",  # missed event uses daily schedule once
            "2024-11-12T04:55:00+01:00",
            True,
            1,
            1,
            BACKUP_CALL,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"recurrence": "never"},
                }
            ],
            "2024-10-26T04:45:00+01:00",
            "2034-11-11T12:00:00+01:00",  # ten years later and still no backups
            "2034-11-12T12:00:00+01:00",
            "2024-10-26T04:45:00+01:00",
            "2024-10-26T04:45:00+01:00",
            None,
            False,
            0,
            0,
            None,
            None,
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"recurrence": "daily"},
                }
            ],
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",  # attempted to create backup but failed
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:55:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            [BackupReaderWriterError("Boom"), None],
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test.test-agent"]},
                    "schedule": {"recurrence": "daily"},
                }
            ],
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:55:00+01:00",
            "2024-11-13T04:55:00+01:00",
            "2024-11-12T04:55:00+01:00",  # attempted to create backup but failed
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:55:00+01:00",
            False,
            1,
            2,
            BACKUP_CALL,
            [Exception("Boom"), None],  # unknown error
        ),
    ],
)
@patch("homeassistant.components.backup.config.random.randint", Mock(return_value=600))
async def test_config_schedule_logic(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    create_backup: AsyncMock,
    commands: list[dict[str, Any]],
    last_completed_automatic_backup: str,
    time_1: str,
    time_2: str,
    attempted_backup_time: str,
    completed_backup_time: str,
    scheduled_backup_time: str,
    additional_backup: bool,
    backup_calls_1: int,
    backup_calls_2: int,
    call_args: Any,
    create_backup_side_effect: list[Exception | None] | None,
) -> None:
    """Test config schedule logic."""
    created_backup: MagicMock = create_backup.return_value[1].result().backup
    created_backup.protected = True

    client = await hass_ws_client(hass)
    storage_data = {
        "backups": [],
        "config": {
            "agents": {},
            "automatic_backups_configured": False,
            "create_backup": {
                "agent_ids": ["test.test-agent"],
                "include_addons": [],
                "include_all_addons": False,
                "include_database": True,
                "include_folders": [],
                "name": "test-name",
                "password": "test-password",
            },
            "retention": {"copies": None, "days": None},
            "last_attempted_automatic_backup": last_completed_automatic_backup,
            "last_completed_automatic_backup": last_completed_automatic_backup,
            "schedule": {
                "days": [],
                "recurrence": "daily",
                "state": "never",
                "time": None,
            },
        },
    }
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": store.STORAGE_VERSION,
        "minor_version": store.STORAGE_VERSION_MINOR,
    }
    create_backup.side_effect = create_backup_side_effect
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-11 12:00:00+01:00")

    await setup_backup_integration(hass, remote_agents=["test.test-agent"])
    await hass.async_block_till_done()

    for command in commands:
        await client.send_json_auto_id(command)
        result = await client.receive_json()
        assert result["success"]

    await client.send_json_auto_id({"type": "backup/info"})
    result = await client.receive_json()
    assert result["result"]["next_automatic_backup"] == scheduled_backup_time
    assert result["result"]["next_automatic_backup_additional"] == additional_backup

    freezer.move_to(time_1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert create_backup.call_count == backup_calls_1
    assert create_backup.call_args == call_args
    async_fire_time_changed(hass, fire_all=True)  # flush out storage save
    await hass.async_block_till_done()
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_attempted_automatic_backup"]
        == attempted_backup_time
    )
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_completed_automatic_backup"]
        == completed_backup_time
    )

    freezer.move_to(time_2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert create_backup.call_count == backup_calls_2
    assert create_backup.call_args == call_args


@pytest.mark.parametrize(
    (
        "command",
        "backups",
        "get_backups_agent_errors",
        "delete_backup_side_effects",
        "last_backup_time",
        "next_time",
        "backup_time",
        "backup_calls",
        "get_backups_calls",
        "delete_calls",
    ),
    [
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": None, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,  # we get backups even if backup retention copies is None
            {},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 3, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 3, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 3, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-5": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {
                "test.test-agent": [call("backup-1")],
                "test.test-agent2": [call("backup-1")],
            },
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 3, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-5": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {
                "test.test-agent": [call("backup-1")],
                "test.test-agent2": [call("backup-1")],
            },
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 2, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-5": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {"test.test-agent": [call("backup-1"), call("backup-2")]},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 2, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {"test.test-agent": BackupAgentError("Boom!")},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {"test.test-agent": [call("backup-1")]},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 2, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {"test.test-agent": BackupAgentError("Boom!")},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {"test.test-agent": [call("backup-1")]},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 1, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-5": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {
                "test.test-agent": [
                    call("backup-1"),
                    call("backup-2"),
                    call("backup-3"),
                ],
                "test.test-agent2": [
                    call("backup-1"),
                    call("backup-2"),
                    call("backup-3"),
                ],
            },
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 1, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-5": MagicMock(
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {
                "test.test-agent": [
                    call("backup-1"),
                    call("backup-2"),
                    call("backup-3"),
                ],
                "test.test-agent2": [call("backup-1"), call("backup-2")],
            },
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 1, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {},
        ),
        (
            {
                "type": "backup/config/update",
                "agents": {
                    "test.test-agent": {
                        "protected": True,
                        "retention": None,
                    },
                    "test.test-agent2": {
                        "protected": True,
                        "retention": {
                            "copies": 1,
                            "days": None,
                        },
                    },
                },
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 3, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-1",
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-2": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-2",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-3": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-3",
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-4": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-4",
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-5": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-5",
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {
                "test.test-agent": [call("backup-1")],
                "test.test-agent2": [call("backup-1"), call("backup-2")],
            },
        ),
        (
            {
                "type": "backup/config/update",
                "agents": {
                    "test.test-agent": {
                        "protected": True,
                        "retention": None,
                    },
                    "test.test-agent2": {
                        "protected": True,
                        "retention": {
                            "copies": 1,
                            "days": None,
                        },
                    },
                },
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": None, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-1",
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-2": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-2",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-3": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-3",
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-4": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-4",
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-5": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-5",
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {
                "test.test-agent2": [call("backup-1"), call("backup-2")],
            },
        ),
        (
            {
                "type": "backup/config/update",
                "agents": {
                    "test.test-agent": {
                        "protected": True,
                        "retention": {
                            "copies": None,
                            "days": None,
                        },
                    },
                    "test.test-agent2": {
                        "protected": True,
                        "retention": None,
                    },
                },
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 2, "days": None},
                "schedule": {"recurrence": "daily"},
            },
            {
                "backup-1": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-1",
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-2": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-2",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-3": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-3",
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-4": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-4",
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-5": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-5",
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            "2024-11-12T04:45:00+01:00",
            1,
            1,
            {
                "test.test-agent2": [call("backup-1")],
            },
        ),
    ],
)
@patch("homeassistant.components.backup.config.BACKUP_START_TIME_JITTER", 0)
async def test_config_retention_copies_logic(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    create_backup: AsyncMock,
    get_backups: AsyncMock,
    command: dict[str, Any],
    backups: dict[str, Any],
    get_backups_agent_errors: dict[str, Exception],
    delete_backup_side_effects: dict[str, Exception],
    last_backup_time: str,
    next_time: str,
    backup_time: str,
    backup_calls: int,
    get_backups_calls: int,
    delete_calls: dict[str, Any],
) -> None:
    """Test config backup retention copies logic."""
    created_backup: MagicMock = create_backup.return_value[1].result().backup
    created_backup.protected = True

    client = await hass_ws_client(hass)
    storage_data = {
        "backups": [],
        "config": {
            "agents": {},
            "automatic_backups_configured": False,
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": ["test-addon"],
                "include_all_addons": False,
                "include_database": True,
                "include_folders": ["media"],
                "name": "test-name",
                "password": "test-password",
            },
            "retention": {"copies": None, "days": None},
            "last_attempted_automatic_backup": None,
            "last_completed_automatic_backup": last_backup_time,
            "schedule": {
                "days": [],
                "recurrence": "daily",
                "state": "never",
                "time": None,
            },
        },
    }
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": store.STORAGE_VERSION,
        "minor_version": store.STORAGE_VERSION_MINOR,
    }
    get_backups.return_value = (backups, get_backups_agent_errors)
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-11 12:00:00+01:00")

    mock_agents = await setup_backup_integration(
        hass, remote_agents=["test.test-agent", "test.test-agent2"]
    )
    await hass.async_block_till_done()

    for agent_id, agent in mock_agents.items():
        agent.async_delete_backup.side_effect = delete_backup_side_effects.get(agent_id)

    await client.send_json_auto_id(command)
    result = await client.receive_json()

    assert result["success"]

    freezer.move_to(next_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert create_backup.call_count == backup_calls
    assert get_backups.call_count == get_backups_calls
    for agent_id, agent in mock_agents.items():
        agent_delete_calls = delete_calls.get(agent_id, [])
        assert agent.async_delete_backup.call_count == len(agent_delete_calls)
        assert agent.async_delete_backup.call_args_list == agent_delete_calls
    async_fire_time_changed(hass, fire_all=True)  # flush out storage save
    await hass.async_block_till_done()
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_attempted_automatic_backup"]
        == backup_time
    )
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_completed_automatic_backup"]
        == backup_time
    )


@pytest.mark.parametrize(
    ("backup_command", "backup_time"),
    [
        (
            {"type": "backup/generate_with_automatic_settings"},
            "2024-11-11T12:00:00+01:00",
        ),
        (
            {"type": "backup/generate", "agent_ids": ["test.test-agent"]},
            None,
        ),
    ],
)
@pytest.mark.parametrize(
    (
        "config_command",
        "backups",
        "get_backups_agent_errors",
        "backup_calls",
        "get_backups_calls",
        "delete_calls",
    ),
    [
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": None, "days": None},
                "schedule": {"recurrence": "never"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            1,
            1,  # we get backups even if backup retention copies is None
            {},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 3, "days": None},
                "schedule": {"recurrence": "never"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            1,
            1,
            {},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 3, "days": None},
                "schedule": {"recurrence": "never"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-5": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            1,
            1,
            {"test.test-agent": [call("backup-1")]},
        ),
        (
            {
                "type": "backup/config/update",
                "create_backup": {"agent_ids": ["test.test-agent"]},
                "retention": {"copies": 2, "days": None},
                "schedule": {"recurrence": "never"},
            },
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-5": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-12T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            1,
            1,
            {"test.test-agent": [call("backup-1"), call("backup-2")]},
        ),
    ],
)
async def test_config_retention_copies_logic_manual_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    create_backup: AsyncMock,
    get_backups: AsyncMock,
    config_command: dict[str, Any],
    backup_command: dict[str, Any],
    backups: dict[str, Any],
    get_backups_agent_errors: dict[str, Exception],
    backup_time: str,
    backup_calls: int,
    get_backups_calls: int,
    delete_calls: dict[str, Any],
) -> None:
    """Test config backup retention copies logic for manual backup."""
    created_backup: MagicMock = create_backup.return_value[1].result().backup
    created_backup.protected = True

    client = await hass_ws_client(hass)
    storage_data = {
        "backups": [],
        "config": {
            "agents": {},
            "automatic_backups_configured": False,
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": ["test-addon"],
                "include_all_addons": False,
                "include_database": True,
                "include_folders": ["media"],
                "name": "test-name",
                "password": "test-password",
            },
            "retention": {"copies": None, "days": None},
            "last_attempted_automatic_backup": None,
            "last_completed_automatic_backup": None,
            "schedule": {
                "days": [],
                "recurrence": "daily",
                "state": "never",
                "time": None,
            },
        },
    }
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": store.STORAGE_VERSION,
        "minor_version": store.STORAGE_VERSION_MINOR,
    }
    get_backups.return_value = (backups, get_backups_agent_errors)
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-11 12:00:00+01:00")

    mock_agents = await setup_backup_integration(
        hass, remote_agents=["test.test-agent"]
    )
    await hass.async_block_till_done()

    await client.send_json_auto_id(config_command)
    result = await client.receive_json()
    assert result["success"]

    # Create a manual backup
    await client.send_json_auto_id(backup_command)
    result = await client.receive_json()
    assert result["success"]

    # Wait for backup creation to complete
    await hass.async_block_till_done()

    assert create_backup.call_count == backup_calls
    assert get_backups.call_count == get_backups_calls
    for agent_id, agent in mock_agents.items():
        agent_delete_calls = delete_calls.get(agent_id, [])
        assert agent.async_delete_backup.call_count == len(agent_delete_calls)
        assert agent.async_delete_backup.call_args_list == agent_delete_calls
    async_fire_time_changed(hass, fire_all=True)  # flush out storage save
    await hass.async_block_till_done()
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_attempted_automatic_backup"]
        == backup_time
    )
    assert (
        hass_storage[DOMAIN]["data"]["config"]["last_completed_automatic_backup"]
        == backup_time
    )


@pytest.mark.parametrize(
    (
        "stored_retained_days",
        "commands",
        "backups",
        "get_backups_agent_errors",
        "delete_backup_side_effects",
        "last_backup_time",
        "start_time",
        "next_time",
        "get_backups_calls",
        "delete_calls",
    ),
    [
        # No config update - cleanup backups older than 2 days
        (
            2,
            [],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {"test.test-agent": [call("backup-1")]},
        ),
        # No config update - No cleanup
        (
            None,
            [],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            0,
            {},
        ),
        # Unchanged config
        (
            2,
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 2},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {"test.test-agent": [call("backup-1")]},
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 2},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {"test.test-agent": [call("backup-1")]},
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 3},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {},
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 2},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {"test.test-agent": [call("backup-1"), call("backup-2")]},
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 2},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {"test-agent": BackupAgentError("Boom!")},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {"test.test-agent": [call("backup-1")]},
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 2},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {"test-agent": BackupAgentError("Boom!")},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {"test.test-agent": [call("backup-1")]},
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 1},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-2": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-3": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                    spec=ManagerBackup,
                ),
                "backup-4": MagicMock(
                    agents={"test.test-agent": MagicMock(spec=AgentBackupStatus)},
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                    spec=ManagerBackup,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {"test.test-agent": [call("backup-1"), call("backup-2")]},
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "test.test-agent": {
                            "protected": True,
                            "retention": {"days": 3},
                        },
                        "test.test-agent2": {
                            "protected": True,
                            "retention": None,
                        },
                    },
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 2},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-1",
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-2": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-2",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-3": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-3",
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-4": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-4",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {
                "test.test-agent": [call("backup-1")],
                "test.test-agent2": [call("backup-1"), call("backup-2")],
            },
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "test.test-agent": {
                            "protected": True,
                            "retention": {"days": 3},
                        },
                        "test.test-agent2": {
                            "protected": True,
                            "retention": None,
                        },
                    },
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": None},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-1",
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-2": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-2",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-3": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-3",
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-4": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-4",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {
                "test.test-agent": [call("backup-1")],
            },
        ),
        (
            None,
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "test.test-agent": {
                            "protected": True,
                            "retention": None,
                        },
                        "test.test-agent2": {
                            "protected": True,
                            "retention": {"copies": None, "days": None},
                        },
                    },
                    "create_backup": {"agent_ids": ["test-agent"]},
                    "retention": {"copies": None, "days": 2},
                    "schedule": {"recurrence": "never"},
                }
            ],
            {
                "backup-1": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-1",
                    date="2024-11-09T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-2": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-2",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-3": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-3",
                    date="2024-11-11T04:45:00+01:00",
                    with_automatic_settings=True,
                ),
                "backup-4": replace(
                    TEST_MANAGER_BACKUP,
                    agents={
                        "test.test-agent": MagicMock(spec=AgentBackupStatus),
                        "test.test-agent2": MagicMock(spec=AgentBackupStatus),
                    },
                    backup_id="backup-4",
                    date="2024-11-10T04:45:00+01:00",
                    with_automatic_settings=False,
                ),
            },
            {},
            {},
            "2024-11-11T04:45:00+01:00",
            "2024-11-11T12:00:00+01:00",
            "2024-11-12T12:00:00+01:00",
            1,
            {
                "test.test-agent": [call("backup-1"), call("backup-2")],
            },
        ),
    ],
)
async def test_config_retention_days_logic(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    get_backups: AsyncMock,
    stored_retained_days: int | None,
    commands: list[dict[str, Any]],
    backups: dict[str, Any],
    get_backups_agent_errors: dict[str, Exception],
    delete_backup_side_effects: dict[str, Exception],
    last_backup_time: str,
    start_time: str,
    next_time: str,
    get_backups_calls: int,
    delete_calls: dict[str, Any],
) -> None:
    """Test config backup retention logic."""
    client = await hass_ws_client(hass)
    storage_data = {
        "backups": [],
        "config": {
            "agents": {},
            "automatic_backups_configured": False,
            "create_backup": {
                "agent_ids": ["test-agent"],
                "include_addons": ["test-addon"],
                "include_all_addons": False,
                "include_database": True,
                "include_folders": ["media"],
                "name": "test-name",
                "password": "test-password",
            },
            "retention": {"copies": None, "days": stored_retained_days},
            "last_attempted_automatic_backup": None,
            "last_completed_automatic_backup": last_backup_time,
            "schedule": {
                "days": [],
                "recurrence": "never",
                "state": "never",
                "time": None,
            },
        },
    }
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": store.STORAGE_VERSION,
        "minor_version": store.STORAGE_VERSION_MINOR,
    }
    get_backups.return_value = (backups, get_backups_agent_errors)
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(start_time)

    mock_agents = await setup_backup_integration(
        hass, remote_agents=["test.test-agent", "test.test-agent2"]
    )
    await hass.async_block_till_done()

    for agent_id, agent in mock_agents.items():
        agent.async_delete_backup.side_effect = delete_backup_side_effects.get(agent_id)

    for command in commands:
        await client.send_json_auto_id(command)
        result = await client.receive_json()
        assert result["success"]

    freezer.move_to(next_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert get_backups.call_count == get_backups_calls
    for agent_id, agent in mock_agents.items():
        agent_delete_calls = delete_calls.get(agent_id, [])
        assert agent.async_delete_backup.call_count == len(agent_delete_calls)
        assert agent.async_delete_backup.call_args_list == agent_delete_calls
    async_fire_time_changed(hass, fire_all=True)  # flush out storage save
    await hass.async_block_till_done()


async def test_configured_agents_unavailable_repair(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test creating and deleting repair issue for configured unavailable agents."""
    issue_id = "automatic_backup_agents_unavailable_test.agent"
    ws_client = await hass_ws_client(hass)
    hass_storage.update(
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "automatic_backups_configured": True,
                        "create_backup": {
                            "agent_ids": ["test.agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": ["mon"],
                            "recurrence": "custom_days",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        }
    )

    await setup_backup_integration(hass)
    get_agents_mock = AsyncMock(return_value=[mock_backup_agent("agent")])
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

    reload_backup_agents = register_listener_mock.call_args[1]["listener"]

    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local", "name": "local"},
        {"agent_id": "test.agent", "name": "agent"},
    ]

    assert not issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)

    # Reload the agents with no agents returned.

    get_agents_mock.return_value = []
    reload_backup_agents()
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local", "name": "local"},
    ]

    assert issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)

    await ws_client.send_json_auto_id({"type": "backup/config/info"})
    result = await ws_client.receive_json()
    assert result["result"]["config"]["create_backup"]["agent_ids"] == ["test.agent"]

    # Update the automatic backup configuration removing the unavailable agent.

    await ws_client.send_json_auto_id(
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["backup.local"]},
        }
    )
    result = await ws_client.receive_json()

    assert not issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)

    await ws_client.send_json_auto_id({"type": "backup/config/info"})
    result = await ws_client.receive_json()
    assert result["result"]["config"]["create_backup"]["agent_ids"] == ["backup.local"]

    # Reload the agents with one agent returned
    # but not configured for automatic backups.

    get_agents_mock.return_value = [mock_backup_agent("agent")]
    reload_backup_agents()
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local", "name": "local"},
        {"agent_id": "test.agent", "name": "agent"},
    ]

    assert not issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)

    await ws_client.send_json_auto_id({"type": "backup/config/info"})
    result = await ws_client.receive_json()
    assert result["result"]["config"]["create_backup"]["agent_ids"] == ["backup.local"]

    # Update the automatic backup configuration and configure the test agent.

    await ws_client.send_json_auto_id(
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["backup.local", "test.agent"]},
        }
    )
    result = await ws_client.receive_json()

    assert not issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)

    await ws_client.send_json_auto_id({"type": "backup/config/info"})
    result = await ws_client.receive_json()
    assert result["result"]["config"]["create_backup"]["agent_ids"] == [
        "backup.local",
        "test.agent",
    ]

    # Reload the agents with no agents returned again.

    get_agents_mock.return_value = []
    reload_backup_agents()
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local", "name": "local"},
    ]

    assert issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)

    await ws_client.send_json_auto_id({"type": "backup/config/info"})
    result = await ws_client.receive_json()
    assert result["result"]["config"]["create_backup"]["agent_ids"] == [
        "backup.local",
        "test.agent",
    ]

    # Update the automatic backup configuration removing all agents.

    await ws_client.send_json_auto_id(
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": []},
        }
    )
    result = await ws_client.receive_json()

    assert not issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)

    await ws_client.send_json_auto_id({"type": "backup/config/info"})
    result = await ws_client.receive_json()
    assert result["result"]["config"]["create_backup"]["agent_ids"] == []


async def test_subscribe_event(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test subscribe event."""
    await setup_backup_integration(hass, with_hassio=False)

    manager = hass.data[DATA_MANAGER]

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    assert await client.receive_json() == snapshot
    assert await client.receive_json() == snapshot

    manager.async_on_backup_event(
        CreateBackupEvent(stage=None, state=CreateBackupState.IN_PROGRESS, reason=None)
    )
    assert await client.receive_json() == snapshot


async def test_subscribe_event_early(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test subscribe event before backup integration has started."""
    async_initialize_backup(hass)
    await setup_backup_integration(hass, with_hassio=False)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    assert await client.receive_json() == snapshot

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    manager = hass.data[DATA_MANAGER]

    manager.async_on_backup_event(
        CreateBackupEvent(stage=None, state=CreateBackupState.IN_PROGRESS, reason=None)
    )
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    ("agent_id", "backup_id", "password"),
    [
        # Invalid agent or backup
        ("no_such_agent", "c0cb53bd", "hunter2"),
        ("backup.local", "no_such_backup", "hunter2"),
        # Legacy backup, which can't be streamed
        ("backup.local", "2bcb3113", "hunter2"),
        # New backup, which can be streamed, try with correct and wrong password
        ("backup.local", "c0cb53bd", "hunter2"),
        ("backup.local", "c0cb53bd", "wrong_password"),
    ],
)
@pytest.mark.usefixtures("mock_backups")
async def test_can_decrypt_on_download(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    agent_id: str,
    backup_id: str,
    password: str,
) -> None:
    """Test can decrypt on download."""
    await setup_backup_integration(hass, with_hassio=False)

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/can_decrypt_on_download",
            "backup_id": backup_id,
            "agent_id": agent_id,
            "password": password,
        }
    )
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "error",
    [
        BackupAgentError,
        BackupNotFound,
    ],
)
@pytest.mark.usefixtures("mock_backups")
async def test_can_decrypt_on_download_with_agent_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    error: Exception,
) -> None:
    """Test can decrypt on download."""

    mock_agents = await setup_backup_integration(
        hass,
        with_hassio=False,
        backups={"test.remote": [TEST_BACKUP_ABC123]},
        remote_agents=["test.remote"],
    )
    client = await hass_ws_client(hass)

    mock_agents["test.remote"].async_download_backup.side_effect = error
    await client.send_json_auto_id(
        {
            "type": "backup/can_decrypt_on_download",
            "backup_id": TEST_BACKUP_ABC123.backup_id,
            "agent_id": "test.remote",
            "password": "hunter2",
        }
    )
    assert await client.receive_json() == snapshot


@pytest.mark.usefixtures("mock_backups")
async def test_can_decrypt_on_download_get_backup_returns_none(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test can decrypt on download when the agent returns None from get_backup."""

    mock_agents = await setup_backup_integration(hass, remote_agents=["test.remote"])
    mock_agents["test.remote"].async_get_backup.return_value = None
    mock_agents["test.remote"].async_get_backup.side_effect = None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/can_decrypt_on_download",
            "backup_id": TEST_BACKUP_ABC123.backup_id,
            "agent_id": "test.remote",
            "password": "hunter2",
        }
    )
    assert await client.receive_json() == snapshot
    assert (
        "Detected that integration 'test' returns None from BackupAgent.async_get_backup."
        in caplog.text
    )
