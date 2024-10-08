"""Tests for the Backup integration."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import TEST_BACKUP, BackupSyncAgentTest, setup_backup_integration

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
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.get_backups",
        return_value={TEST_BACKUP.slug: TEST_BACKUP},
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        assert snapshot == await client.receive_json()


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
        "homeassistant.components.backup.manager.BackupManager.remove_backup",
    ):
        await client.send_json_auto_id({"type": "backup/remove", "slug": "abc123"})
        assert snapshot == await client.receive_json()


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_generate(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test generating a backup."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.generate_backup",
            return_value=TEST_BACKUP,
        ),
        patch(
            "homeassistant.components.backup.manager.BackupManager.sync_backup",
        ) as sync_backup_mock,
    ):
        await client.send_json_auto_id({"type": "backup/generate"})
        assert snapshot == await client.receive_json()
        assert with_hassio or sync_backup_mock.called


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
        "homeassistant.components.backup.manager.BackupManager.post_backup_actions",
    ):
        await client.send_json_auto_id({"type": "backup/end"})
        assert snapshot == await client.receive_json()


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
        "homeassistant.components.backup.manager.BackupManager.pre_backup_actions",
    ):
        await client.send_json_auto_id({"type": "backup/start"})
        assert snapshot == await client.receive_json()


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError(),
        HomeAssistantError("Boom"),
        Exception("Boom"),
    ],
)
async def test_backup_end_excepion(
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
        "homeassistant.components.backup.manager.BackupManager.post_backup_actions",
        side_effect=exception,
    ):
        await client.send_json_auto_id({"type": "backup/end"})
        assert snapshot == await client.receive_json()


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError(),
        HomeAssistantError("Boom"),
        Exception("Boom"),
    ],
)
async def test_backup_start_excepion(
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
        "homeassistant.components.backup.manager.BackupManager.pre_backup_actions",
        side_effect=exception,
    ):
        await client.send_json_auto_id({"type": "backup/start"})
        assert snapshot == await client.receive_json()


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
    manager = hass.data["backup"]
    manager.sync_agents = {"domain.test": BackupSyncAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    assert snapshot == await client.receive_json()


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_agents_synced(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test getting backup agents synced details."""
    await setup_backup_integration(hass, with_hassio=with_hassio)
    manager = hass.data["backup"]
    manager.sync_agents = {"domain.test": BackupSyncAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/synced"})
    assert snapshot == await client.receive_json()


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
    """Test getting backup agents synced details."""
    await setup_backup_integration(hass, with_hassio=with_hassio)
    manager = hass.data["backup"]
    manager.sync_agents = {"domain.test": BackupSyncAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "slug": "abc123",
            "agent": "domain.test",
            "sync_id": "abc123",
        }
    )
    with patch.object(BackupSyncAgentTest, "async_download_backup") as download_mock:
        assert await client.receive_json()
        assert snapshot == download_mock.call_args


async def test_agents_download_exception(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting backup agents synced details."""
    await setup_backup_integration(hass)
    manager = hass.data["backup"]
    manager.sync_agents = {"domain.test": BackupSyncAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "slug": "abc123",
            "agent": "domain.test",
            "sync_id": "abc123",
        }
    )
    with patch.object(BackupSyncAgentTest, "async_download_backup") as download_mock:
        download_mock.side_effect = Exception("Boom")
        assert snapshot == await client.receive_json()
