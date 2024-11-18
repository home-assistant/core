"""Tests for the Backup integration."""

from pathlib import Path
from typing import Any
from unittest.mock import ANY, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup import BaseBackup
from homeassistant.components.backup.agent import BackupAgentUnreachableError
from homeassistant.components.backup.const import DATA_MANAGER, DOMAIN
from homeassistant.components.backup.manager import NewBackup
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import TEST_LOCAL_BACKUP, BackupAgentTest, setup_backup_integration

from tests.typing import WebSocketGenerator


@pytest.fixture
def sync_access_token_proxy(
    access_token_fixture_name: str,
    request: pytest.FixtureRequest,
) -> str:
    """Non-async proxy for the *_access_token fixture.

    Workaround for https://github.com/pytest-dev/pytest-asyncio/issues/112
    """
    return request.getfixturevalue(access_token_fixture_name)


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test getting backup info."""
    await setup_backup_integration(
        hass, with_hassio=with_hassio, backups=[TEST_LOCAL_BACKUP]
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
    await setup_backup_integration(hass, with_hassio=False, backups=[TEST_LOCAL_BACKUP])
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch.object(BackupAgentTest, "async_list_backups", side_effect=side_effect):
        await client.send_json_auto_id({"type": "backup/info"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "backup_content",
    [
        pytest.param([TEST_LOCAL_BACKUP], id="with_backup_content"),
        pytest.param(None, id="without_backup_content"),
    ],
)
@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_details(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
    backup_content: BaseBackup | None,
) -> None:
    """Test getting backup info."""
    await setup_backup_integration(
        hass, with_hassio=with_hassio, backups=backup_content
    )

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch("pathlib.Path.exists", return_value=True):
        await client.send_json_auto_id({"type": "backup/details", "slug": "abc123"})
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
    await setup_backup_integration(hass, with_hassio=False, backups=[TEST_LOCAL_BACKUP])
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch.object(BackupAgentTest, "async_get_backup", side_effect=side_effect),
    ):
        await client.send_json_auto_id({"type": "backup/details", "slug": "abc123"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_remove(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test removing a backup file."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_remove_backup",
    ):
        await client.send_json_auto_id({"type": "backup/remove", "slug": "abc123"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"password": "abc123"},
    ],
)
@pytest.mark.parametrize(
    ("with_hassio", "number_of_messages"),
    [
        pytest.param(True, 1, id="with_hassio"),
        pytest.param(False, 2, id="without_hassio"),
    ],
)
@pytest.mark.usefixtures("mock_backup_generation")
async def test_generate(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    data: dict[str, Any] | None,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
    number_of_messages: int,
) -> None:
    """Test generating a backup."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    freezer.move_to("2024-11-13 12:01:00+01:00")
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {"type": "backup/generate", **{"agent_ids": ["backup.local"]} | (data or {})}
    )
    for _ in range(number_of_messages):
        assert await client.receive_json() == snapshot


@pytest.mark.usefixtures("mock_backup_generation")
@pytest.mark.parametrize(
    ("params", "expected_extra_call_params"),
    [
        ({"agent_ids": ["backup.local"]}, {"agent_ids": ["backup.local"]}),
        (
            {
                "addons_included": ["ssl"],
                "agent_ids": ["backup.local"],
                "database_included": False,
                "folders_included": ["media"],
                "name": "abc123",
            },
            {
                "addons_included": ["ssl"],
                "agent_ids": ["backup.local"],
                "database_included": False,
                "folders_included": ["media"],
                "name": "abc123",
            },
        ),
    ],
)
async def test_generate_without_hassio(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    params: dict,
    expected_extra_call_params: tuple,
) -> None:
    """Test generating a backup."""
    await setup_backup_integration(hass, with_hassio=False)

    client = await hass_ws_client(hass)
    freezer.move_to("2024-11-13 12:01:00+01:00")
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
        return_value=NewBackup("abc123"),
    ) as generate_backup:
        await client.send_json_auto_id({"type": "backup/generate"} | params)
        assert await client.receive_json() == snapshot
        generate_backup.assert_called_once_with(
            **{
                "addons_included": None,
                "database_included": True,
                "folders_included": None,
                "name": None,
                "on_progress": ANY,
                "password": None,
            }
            | expected_extra_call_params
        )


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_restore(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test calling the restore command."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_restore_backup",
    ):
        await client.send_json_auto_id(
            {"type": "backup/restore", "slug": "abc123", "agent_id": "backup.local"}
        )
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


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test getting backup agents info."""
    await setup_backup_integration(hass, with_hassio=with_hassio)
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test backup agents list backups details."""
    await setup_backup_integration(hass, with_hassio=with_hassio)
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/list_backups"})
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_agents_download(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test WS command to start downloading a backup."""
    await setup_backup_integration(hass, with_hassio=with_hassio)
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "slug": "abc123",
            "agent_id": "domain.test",
            "backup_id": "abc123",
        }
    )
    with patch.object(BackupAgentTest, "async_download_backup") as download_mock:
        assert await client.receive_json() == snapshot
        assert download_mock.call_args[1] == {
            "id": "abc123",
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
            "slug": "abc123",
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
            "slug": "abc123",
            "agent_id": "domain.test",
            "backup_id": "abc123",
        }
    )
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "storage_data",
    [
        {},
        {"last_automatic_backup": "2024-10-26T02:00:00+00:00", "max_copies": 3},
        {"last_automatic_backup": None, "max_copies": 3},
        {"last_automatic_backup": "2024-10-26T02:00:00+00:00", "max_copies": None},
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


async def test_config_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test updating the backup config."""
    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot

    await client.send_json_auto_id({"type": "backup/config/update", "max_copies": 5})
    result = await client.receive_json()

    assert result["success"]

    await client.send_json_auto_id({"type": "backup/config/info"})
    assert await client.receive_json() == snapshot
