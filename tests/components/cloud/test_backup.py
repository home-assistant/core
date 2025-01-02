"""Test the cloud backup platform."""

from collections.abc import AsyncGenerator, AsyncIterator, Generator
from io import StringIO
from typing import Any
from unittest.mock import Mock, PropertyMock, patch

from aiohttp import ClientError
from hass_nabucasa import CloudError
import pytest
from yarl import URL

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AddonInfo,
    AgentBackup,
    Folder,
)
from homeassistant.components.cloud import DOMAIN
from homeassistant.components.cloud.backup import async_register_backup_agents_listener
from homeassistant.components.cloud.const import EVENT_CLOUD_EVENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator, MagicMock, WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    cloud: MagicMock,
    cloud_logged_in: None,
) -> AsyncGenerator[None]:
    """Set up cloud integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
        yield


@pytest.fixture
def mock_delete_file() -> Generator[MagicMock]:
    """Mock list files."""
    with patch(
        "homeassistant.components.cloud.backup.async_files_delete_file",
        spec_set=True,
    ) as delete_file:
        yield delete_file


@pytest.fixture
def mock_get_download_details() -> Generator[MagicMock]:
    """Mock list files."""
    with patch(
        "homeassistant.components.cloud.backup.async_files_download_details",
        spec_set=True,
    ) as download_details:
        download_details.return_value = {
            "url": (
                "https://blabla.cloudflarestorage.com/blabla/backup/"
                "462e16810d6841228828d9dd2f9e341e.tar?X-Amz-Algorithm=blah"
            ),
        }
        yield download_details


@pytest.fixture
def mock_get_upload_details() -> Generator[MagicMock]:
    """Mock list files."""
    with patch(
        "homeassistant.components.cloud.backup.async_files_upload_details",
        spec_set=True,
    ) as download_details:
        download_details.return_value = {
            "url": (
                "https://blabla.cloudflarestorage.com/blabla/backup/"
                "ea5c969e492c49df89d432a1483b8dc3.tar?X-Amz-Algorithm=blah"
            ),
            "headers": {
                "content-md5": "HOhSM3WZkpHRYGiz4YRGIQ==",
                "x-amz-meta-storage-type": "backup",
                "x-amz-meta-b64json": (
                    "eyJhZGRvbnMiOltdLCJiYWNrdXBfaWQiOiJjNDNiNWU2MCIsImRhdGUiOiIyMDI0LT"
                    "EyLTAzVDA0OjI1OjUwLjMyMDcwMy0wNTowMCIsImRhdGFiYXNlX2luY2x1ZGVkIjpm"
                    "YWxzZSwiZm9sZGVycyI6W10sImhvbWVhc3Npc3RhbnRfaW5jbHVkZWQiOnRydWUsIm"
                    "hvbWVhc3Npc3RhbnRfdmVyc2lvbiI6IjIwMjQuMTIuMC5kZXYwIiwibmFtZSI6ImVy"
                    "aWsiLCJwcm90ZWN0ZWQiOnRydWUsInNpemUiOjM1NjI0OTYwfQ=="
                ),
            },
        }
        yield download_details


@pytest.fixture
def mock_list_files() -> Generator[MagicMock]:
    """Mock list files."""
    with patch(
        "homeassistant.components.cloud.backup.async_files_list", spec_set=True
    ) as list_files:
        list_files.return_value = [
            {
                "Key": "462e16810d6841228828d9dd2f9e341e.tar",
                "LastModified": "2024-11-22T10:49:01.182Z",
                "Size": 34519040,
                "Metadata": {
                    "addons": [],
                    "backup_id": "23e64aec",
                    "date": "2024-11-22T11:48:48.727189+01:00",
                    "database_included": True,
                    "extra_metadata": {},
                    "folders": [],
                    "homeassistant_included": True,
                    "homeassistant_version": "2024.12.0.dev0",
                    "name": "Core 2024.12.0.dev0",
                    "protected": False,
                    "size": 34519040,
                    "storage-type": "backup",
                },
            }
        ]
        yield list_files


@pytest.fixture
def cloud_logged_in(cloud: MagicMock):
    """Mock cloud logged in."""
    type(cloud).is_logged_in = PropertyMock(return_value=True)


async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup agent info."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [{"agent_id": "backup.local"}, {"agent_id": "cloud.cloud"}],
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    cloud: MagicMock,
    mock_list_files: Mock,
) -> None:
    """Test agent list backups."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()
    mock_list_files.assert_called_once_with(cloud, storage_type="backup")

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        {
            "addons": [],
            "backup_id": "23e64aec",
            "date": "2024-11-22T11:48:48.727189+01:00",
            "database_included": True,
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0.dev0",
            "name": "Core 2024.12.0.dev0",
            "protected": False,
            "size": 34519040,
            "agent_ids": ["cloud.cloud"],
            "failed_agent_ids": [],
            "with_automatic_settings": None,
        }
    ]


@pytest.mark.parametrize("side_effect", [ClientError, CloudError])
async def test_agents_list_backups_fail_cloud(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    cloud: MagicMock,
    mock_list_files: Mock,
    side_effect: Exception,
) -> None:
    """Test agent list backups."""
    client = await hass_ws_client(hass)
    mock_list_files.side_effect = side_effect

    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_errors": {"cloud.cloud": "Failed to list backups"},
        "backups": [],
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
    }


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (
            "23e64aec",
            {
                "addons": [],
                "backup_id": "23e64aec",
                "date": "2024-11-22T11:48:48.727189+01:00",
                "database_included": True,
                "folders": [],
                "homeassistant_included": True,
                "homeassistant_version": "2024.12.0.dev0",
                "name": "Core 2024.12.0.dev0",
                "protected": False,
                "size": 34519040,
                "agent_ids": ["cloud.cloud"],
                "failed_agent_ids": [],
                "with_automatic_settings": None,
            },
        ),
        (
            "12345",
            None,
        ),
    ],
    ids=["found", "not_found"],
)
async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    cloud: MagicMock,
    backup_id: str,
    expected_result: dict[str, Any] | None,
    mock_list_files: Mock,
) -> None:
    """Test agent get backup."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()
    mock_list_files.assert_called_once_with(cloud, storage_type="backup")

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == expected_result


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_get_download_details: Mock,
) -> None:
    """Test agent download backup."""
    client = await hass_client()
    backup_id = "23e64aec"

    aioclient_mock.get(
        mock_get_download_details.return_value["url"], content=b"backup data"
    )

    resp = await client.get(f"/api/backup/download/{backup_id}?agent_id=cloud.cloud")
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"


@pytest.mark.parametrize("side_effect", [ClientError, CloudError])
@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_download_fail_cloud(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_get_download_details: Mock,
    side_effect: Exception,
) -> None:
    """Test agent download backup, when cloud user is logged in."""
    client = await hass_client()
    backup_id = "23e64aec"
    mock_get_download_details.side_effect = side_effect

    resp = await client.get(f"/api/backup/download/{backup_id}?agent_id=cloud.cloud")
    assert resp.status == 500
    content = await resp.content.read()
    assert "Failed to get download details" in content.decode()


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_download_fail_get(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_get_download_details: Mock,
) -> None:
    """Test agent download backup, when cloud user is logged in."""
    client = await hass_client()
    backup_id = "23e64aec"

    aioclient_mock.get(mock_get_download_details.return_value["url"], status=500)

    resp = await client.get(f"/api/backup/download/{backup_id}?agent_id=cloud.cloud")
    assert resp.status == 500
    content = await resp.content.read()
    assert "Failed to download backup" in content.decode()


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_download_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test agent download backup raises error if not found."""
    client = await hass_client()
    backup_id = "1234"

    resp = await client.get(f"/api/backup/download/{backup_id}?agent_id=cloud.cloud")
    assert resp.status == 404
    assert await resp.content.read() == b""


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_get_upload_details: Mock,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    backup_id = "test-backup"
    test_backup = AgentBackup(
        addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
        backup_id=backup_id,
        database_included=True,
        date="1970-01-01T00:00:00.000Z",
        extra_metadata={},
        folders=[Folder.MEDIA, Folder.SHARE],
        homeassistant_included=True,
        homeassistant_version="2024.12.0",
        name="Test",
        protected=True,
        size=0,
    )
    aioclient_mock.put(mock_get_upload_details.return_value["url"])

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO("test")},
        )

    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1] == URL(
        mock_get_upload_details.return_value["url"]
    )
    assert isinstance(aioclient_mock.mock_calls[-1][2], AsyncIterator)

    assert resp.status == 201
    assert f"Uploading backup {backup_id}" in caplog.text


@pytest.mark.parametrize("put_mock_kwargs", [{"status": 500}, {"exc": TimeoutError}])
@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_upload_fail_put(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    mock_get_upload_details: Mock,
    put_mock_kwargs: dict[str, Any],
) -> None:
    """Test agent upload backup fails."""
    client = await hass_client()
    backup_id = "test-backup"
    test_backup = AgentBackup(
        addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
        backup_id=backup_id,
        database_included=True,
        date="1970-01-01T00:00:00.000Z",
        extra_metadata={},
        folders=[Folder.MEDIA, Folder.SHARE],
        homeassistant_included=True,
        homeassistant_version="2024.12.0",
        name="Test",
        protected=True,
        size=0,
    )
    aioclient_mock.put(mock_get_upload_details.return_value["url"], **put_mock_kwargs)

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO("test")},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    store_backups = hass_storage[BACKUP_DOMAIN]["data"]["backups"]
    assert len(store_backups) == 1
    stored_backup = store_backups[0]
    assert stored_backup["backup_id"] == backup_id
    assert stored_backup["failed_agent_ids"] == ["cloud.cloud"]


@pytest.mark.parametrize("side_effect", [ClientError, CloudError])
@pytest.mark.usefixtures("cloud_logged_in")
async def test_agents_upload_fail_cloud(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    mock_get_upload_details: Mock,
    side_effect: Exception,
) -> None:
    """Test agent upload backup, when cloud user is logged in."""
    client = await hass_client()
    backup_id = "test-backup"
    mock_get_upload_details.side_effect = side_effect
    test_backup = AgentBackup(
        addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
        backup_id=backup_id,
        database_included=True,
        date="1970-01-01T00:00:00.000Z",
        extra_metadata={},
        folders=[Folder.MEDIA, Folder.SHARE],
        homeassistant_included=True,
        homeassistant_version="2024.12.0",
        name="Test",
        protected=True,
        size=0,
    )
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO("test")},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    store_backups = hass_storage[BACKUP_DOMAIN]["data"]["backups"]
    assert len(store_backups) == 1
    stored_backup = store_backups[0]
    assert stored_backup["backup_id"] == backup_id
    assert stored_backup["failed_agent_ids"] == ["cloud.cloud"]


async def test_agents_upload_not_protected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test agent upload backup, when cloud user is logged in."""
    client = await hass_client()
    backup_id = "test-backup"
    test_backup = AgentBackup(
        addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
        backup_id=backup_id,
        database_included=True,
        date="1970-01-01T00:00:00.000Z",
        extra_metadata={},
        folders=[Folder.MEDIA, Folder.SHARE],
        homeassistant_included=True,
        homeassistant_version="2024.12.0",
        name="Test",
        protected=False,
        size=0,
    )
    with (
        patch("pathlib.Path.open"),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
    ):
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO("test")},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    store_backups = hass_storage[BACKUP_DOMAIN]["data"]["backups"]
    assert len(store_backups) == 1
    stored_backup = store_backups[0]
    assert stored_backup["backup_id"] == backup_id
    assert stored_backup["failed_agent_ids"] == ["cloud.cloud"]


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_delete_file: Mock,
) -> None:
    """Test agent delete backup."""
    client = await hass_ws_client(hass)
    backup_id = "23e64aec"

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    mock_delete_file.assert_called_once()


@pytest.mark.parametrize("side_effect", [ClientError, CloudError])
@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_delete_fail_cloud(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_delete_file: Mock,
    side_effect: Exception,
) -> None:
    """Test agent delete backup."""
    client = await hass_ws_client(hass)
    backup_id = "23e64aec"
    mock_delete_file.side_effect = side_effect

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_errors": {"cloud.cloud": "Failed to delete backup"}
    }


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_delete_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test agent download backup raises error if not found."""
    client = await hass_ws_client(hass)
    backup_id = "1234"

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}


@pytest.mark.parametrize("event_type", ["login", "logout"])
async def test_calling_listener_on_login_logout(
    hass: HomeAssistant,
    event_type: str,
) -> None:
    """Test calling listener for login and logout events."""
    listener = MagicMock()
    async_register_backup_agents_listener(hass, listener=listener)

    assert listener.call_count == 0
    async_dispatcher_send(hass, EVENT_CLOUD_EVENT, {"type": event_type})
    await hass.async_block_till_done()

    assert listener.call_count == 1


async def test_not_calling_listener_after_unsub(hass: HomeAssistant) -> None:
    """Test only calling listener until unsub."""
    listener = MagicMock()
    unsub = async_register_backup_agents_listener(hass, listener=listener)

    assert listener.call_count == 0
    async_dispatcher_send(hass, EVENT_CLOUD_EVENT, {"type": "login"})
    await hass.async_block_till_done()
    assert listener.call_count == 1

    unsub()

    async_dispatcher_send(hass, EVENT_CLOUD_EVENT, {"type": "login"})
    await hass.async_block_till_done()
    assert listener.call_count == 1


async def test_not_calling_listener_with_unknown_event_type(
    hass: HomeAssistant,
) -> None:
    """Test not calling listener if we did not get the expected event type."""
    listener = MagicMock()
    async_register_backup_agents_listener(hass, listener=listener)

    assert listener.call_count == 0
    async_dispatcher_send(hass, EVENT_CLOUD_EVENT, {"type": "unknown"})
    await hass.async_block_till_done()
    assert listener.call_count == 0
