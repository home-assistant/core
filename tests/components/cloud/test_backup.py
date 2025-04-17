"""Test the cloud backup platform."""

from collections.abc import AsyncGenerator, Generator
from io import StringIO
from typing import Any
from unittest.mock import ANY, Mock, PropertyMock, patch

from aiohttp import ClientError, ClientResponseError
from hass_nabucasa import CloudError
from hass_nabucasa.api import CloudApiError, CloudApiNonRetryableError
from hass_nabucasa.files import FilesError, StorageType
import pytest

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
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component
from homeassistant.util.aiohttp import MockStreamReader

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator, MagicMock, WebSocketGenerator


class MockStreamReaderChunked(MockStreamReader):
    """Mock a stream reader with simulated chunked data."""

    async def readchunk(self) -> tuple[bytes, bool]:
        """Read bytes."""
        return (self._content.read(), False)


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    cloud: MagicMock,
    cloud_logged_in: None,
) -> AsyncGenerator[None]:
    """Set up cloud and backup integrations."""
    async_initialize_backup(hass)
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
            },
            {
                "Key": "462e16810d6841228828d9dd2f9e341f.tar",
                "LastModified": "2024-11-22T10:49:01.182Z",
                "Size": 34519040,
                "Metadata": {
                    "addons": [],
                    "backup_id": "23e64aed",
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
            },
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
        "agents": [
            {"agent_id": "backup.local", "name": "local"},
            {"agent_id": "cloud.cloud", "name": "cloud"},
        ],
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
            "agents": {"cloud.cloud": {"protected": False, "size": 34519040}},
            "backup_id": "23e64aec",
            "date": "2024-11-22T11:48:48.727189+01:00",
            "database_included": True,
            "extra_metadata": {},
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0.dev0",
            "name": "Core 2024.12.0.dev0",
            "failed_agent_ids": [],
            "with_automatic_settings": None,
        },
        {
            "addons": [],
            "agents": {"cloud.cloud": {"protected": False, "size": 34519040}},
            "backup_id": "23e64aed",
            "date": "2024-11-22T11:48:48.727189+01:00",
            "database_included": True,
            "extra_metadata": {},
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0.dev0",
            "name": "Core 2024.12.0.dev0",
            "failed_agent_ids": [],
            "with_automatic_settings": None,
        },
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
        "last_action_event": None,
        "next_automatic_backup": None,
        "next_automatic_backup_additional": False,
        "state": "idle",
    }


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (
            "23e64aec",
            {
                "addons": [],
                "agents": {"cloud.cloud": {"protected": False, "size": 34519040}},
                "backup_id": "23e64aec",
                "date": "2024-11-22T11:48:48.727189+01:00",
                "database_included": True,
                "extra_metadata": {},
                "folders": [],
                "homeassistant_included": True,
                "homeassistant_version": "2024.12.0.dev0",
                "name": "Core 2024.12.0.dev0",
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
    cloud: Mock,
) -> None:
    """Test agent download backup."""
    client = await hass_client()
    backup_id = "23e64aec"

    cloud.files.download.return_value = MockStreamReaderChunked(b"backup data")

    resp = await client.get(f"/api/backup/download/{backup_id}?agent_id=cloud.cloud")
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"
    cloud.files.download.assert_called_once_with(
        filename="462e16810d6841228828d9dd2f9e341e.tar",
        storage_type=StorageType.BACKUP,
    )


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_download_fail_get(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    cloud: Mock,
) -> None:
    """Test agent download backup, when cloud user is logged in."""
    client = await hass_client()
    backup_id = "23e64aec"

    cloud.files.download.side_effect = FilesError("Oh no :(")

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
    cloud: Mock,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    backup_data = "test"
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
        size=len(backup_data),
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
        mocked_open.return_value.read = Mock(side_effect=[backup_data.encode(), b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO(backup_data)},
        )

    cloud.files.upload.assert_called_once_with(
        storage_type=StorageType.BACKUP,
        open_stream=ANY,
        filename=f"{cloud.client.prefs.instance_id}.tar",
        base64md5hash=ANY,
        metadata=ANY,
        size=ANY,
    )
    metadata = cloud.files.upload.mock_calls[-1].kwargs["metadata"]
    assert metadata["backup_id"] == backup_id

    assert resp.status == 201
    assert f"Uploading backup {backup_id}" in caplog.text


@pytest.mark.parametrize("side_effect", [FilesError("Boom!"), CloudError("Boom!")])
@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_upload_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    side_effect: Exception,
    cloud: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent upload backup fails."""
    client = await hass_client()
    backup_data = "test"
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
        size=len(backup_data),
    )

    cloud.files.upload.side_effect = side_effect

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
        patch("homeassistant.components.cloud.backup.asyncio.sleep"),
        patch("homeassistant.components.cloud.backup.random.randint", return_value=60),
        patch("homeassistant.components.cloud.backup._RETRY_LIMIT", 2),
    ):
        mocked_open.return_value.read = Mock(side_effect=[backup_data.encode(), b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO(backup_data)},
        )
        await hass.async_block_till_done()

    assert "Failed to upload backup, retrying (2/2) in 60s" in caplog.text
    assert resp.status == 201
    assert cloud.files.upload.call_count == 2
    store_backups = hass_storage[BACKUP_DOMAIN]["data"]["backups"]
    assert len(store_backups) == 1
    stored_backup = store_backups[0]
    assert stored_backup["backup_id"] == backup_id
    assert stored_backup["failed_agent_ids"] == ["cloud.cloud"]


@pytest.mark.parametrize(
    ("side_effect", "logmsg"),
    [
        (
            CloudApiNonRetryableError("Boom!", code="NC-SH-FH-03"),
            "The backup size of 13.37GB is too large to be uploaded to Home Assistant Cloud",
        ),
        (
            CloudApiNonRetryableError("Boom!", code="NC-CE-01"),
            "Failed to upload backup Boom!",
        ),
    ],
)
@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_upload_fail_non_retryable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    side_effect: Exception,
    logmsg: str,
    cloud: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent upload backup fails with non-retryable error."""
    client = await hass_client()
    backup_data = "test"
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
        size=14358124749,
    )

    cloud.files.upload.side_effect = side_effect

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
        patch("homeassistant.components.cloud.backup.calculate_b64md5"),
    ):
        mocked_open.return_value.read = Mock(side_effect=[backup_data.encode(), b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO(backup_data)},
        )
        await hass.async_block_till_done()

    assert logmsg in caplog.text
    assert resp.status == 201
    assert cloud.files.upload.call_count == 1
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
    backup_data = "test"
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
        size=len(backup_data),
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
            data={"file": StringIO(backup_data)},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    store_backups = hass_storage[BACKUP_DOMAIN]["data"]["backups"]
    assert len(store_backups) == 1
    stored_backup = store_backups[0]
    assert stored_backup["backup_id"] == backup_id
    assert stored_backup["failed_agent_ids"] == ["cloud.cloud"]


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_upload_not_subscribed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    cloud: Mock,
) -> None:
    """Test upload backup when cloud user is not subscribed."""
    cloud.subscription_expired = True
    client = await hass_client()
    backup_data = "test"
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
        size=len(backup_data),
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
        mocked_open.return_value.read = Mock(side_effect=[backup_data.encode(), b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO(backup_data)},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    assert cloud.files.upload.call_count == 0
    store_backups = hass_storage[BACKUP_DOMAIN]["data"]["backups"]
    assert len(store_backups) == 1
    stored_backup = store_backups[0]
    assert stored_backup["backup_id"] == backup_id
    assert stored_backup["failed_agent_ids"] == ["cloud.cloud"]


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_upload_not_subscribed_midway(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    cloud: Mock,
) -> None:
    """Test upload backup when cloud subscription expires during the call."""
    client = await hass_client()
    backup_data = "test"
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
        size=len(backup_data),
    )

    async def mock_upload(*args: Any, **kwargs: Any) -> None:
        """Mock file upload."""
        cloud.subscription_expired = True
        raise CloudApiError(
            "Boom!", orig_exc=ClientResponseError(Mock(), Mock(), status=403)
        )

    cloud.files.upload.side_effect = mock_upload

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
        mocked_open.return_value.read = Mock(side_effect=[backup_data.encode(), b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO(backup_data)},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    assert cloud.files.upload.call_count == 1
    store_backups = hass_storage[BACKUP_DOMAIN]["data"]["backups"]
    assert len(store_backups) == 1
    stored_backup = store_backups[0]
    assert stored_backup["backup_id"] == backup_id
    assert stored_backup["failed_agent_ids"] == ["cloud.cloud"]


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_upload_wrong_size(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    cloud: Mock,
) -> None:
    """Test agent upload backup with the wrong size."""
    client = await hass_client()
    backup_data = "test"
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
        size=len(backup_data) - 1,
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
        mocked_open.return_value.read = Mock(side_effect=[backup_data.encode(), b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=cloud.cloud",
            data={"file": StringIO(backup_data)},
        )

    assert len(cloud.files.upload.mock_calls) == 0

    assert resp.status == 201
    assert "Upload failed for cloud.cloud" in caplog.text


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    cloud: Mock,
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
    mock_delete_file.assert_called_once_with(
        cloud,
        filename="462e16810d6841228828d9dd2f9e341e.tar",
        storage_type=StorageType.BACKUP,
    )


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
