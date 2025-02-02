"""Test supervisor backup functionality."""

from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Coroutine,
    Generator,
)
from dataclasses import replace
from datetime import datetime
from io import StringIO
import os
from pathlib import PurePath
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock, patch
from uuid import UUID

from aiohasupervisor.exceptions import (
    SupervisorBadRequestError,
    SupervisorError,
    SupervisorNotFoundError,
)
from aiohasupervisor.models import (
    backups as supervisor_backups,
    jobs as supervisor_jobs,
    mounts as supervisor_mounts,
)
from aiohasupervisor.models.mounts import MountsInfo
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AddonInfo,
    AgentBackup,
    BackupAgent,
    BackupAgentPlatformProtocol,
    Folder,
)
from homeassistant.components.hassio import DOMAIN
from homeassistant.components.hassio.backup import (
    LOCATION_CLOUD_BACKUP,
    LOCATION_LOCAL,
    RESTORE_JOB_ID_ENV,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON

from tests.common import mock_platform
from tests.typing import ClientSessionGenerator, WebSocketGenerator

TEST_BACKUP = supervisor_backups.Backup(
    compressed=False,
    content=supervisor_backups.BackupContent(
        addons=["ssl"],
        folders=[supervisor_backups.Folder.SHARE],
        homeassistant=True,
    ),
    date=datetime.fromisoformat("1970-01-01T00:00:00Z"),
    location=None,
    location_attributes={
        LOCATION_LOCAL: supervisor_backups.BackupLocationAttributes(
            protected=False, size_bytes=1048576
        )
    },
    locations={None},
    name="Test",
    protected=False,
    size=1.0,
    size_bytes=1048576,
    slug="abc123",
    type=supervisor_backups.BackupType.PARTIAL,
)
TEST_BACKUP_DETAILS = supervisor_backups.BackupComplete(
    addons=[
        supervisor_backups.BackupAddon(
            name="Terminal & SSH",
            size=0.0,
            slug="core_ssh",
            version="9.14.0",
        )
    ],
    compressed=TEST_BACKUP.compressed,
    date=TEST_BACKUP.date,
    extra=None,
    folders=[supervisor_backups.Folder.SHARE],
    homeassistant_exclude_database=False,
    homeassistant="2024.12.0",
    location=TEST_BACKUP.location,
    location_attributes=TEST_BACKUP.location_attributes,
    locations=TEST_BACKUP.locations,
    name=TEST_BACKUP.name,
    protected=TEST_BACKUP.protected,
    repositories=[],
    size=TEST_BACKUP.size,
    size_bytes=TEST_BACKUP.size_bytes,
    slug=TEST_BACKUP.slug,
    supervisor_version="2024.11.2",
    type=TEST_BACKUP.type,
)

TEST_BACKUP_2 = supervisor_backups.Backup(
    compressed=False,
    content=supervisor_backups.BackupContent(
        addons=["ssl"],
        folders=["share"],
        homeassistant=False,
    ),
    date=datetime.fromisoformat("1970-01-01T00:00:00Z"),
    location=None,
    location_attributes={
        LOCATION_LOCAL: supervisor_backups.BackupLocationAttributes(
            protected=False, size_bytes=1048576
        )
    },
    locations={None},
    name="Test",
    protected=False,
    size=1.0,
    size_bytes=1048576,
    slug="abc123",
    type=supervisor_backups.BackupType.PARTIAL,
)
TEST_BACKUP_DETAILS_2 = supervisor_backups.BackupComplete(
    addons=[
        supervisor_backups.BackupAddon(
            name="Terminal & SSH",
            size=0.0,
            slug="core_ssh",
            version="9.14.0",
        )
    ],
    compressed=TEST_BACKUP_2.compressed,
    date=TEST_BACKUP_2.date,
    extra=None,
    folders=["share"],
    homeassistant_exclude_database=False,
    homeassistant=None,
    location=TEST_BACKUP_2.location,
    location_attributes=TEST_BACKUP_2.location_attributes,
    locations=TEST_BACKUP_2.locations,
    name=TEST_BACKUP_2.name,
    protected=TEST_BACKUP_2.protected,
    repositories=[],
    size=TEST_BACKUP_2.size,
    size_bytes=TEST_BACKUP_2.size_bytes,
    slug=TEST_BACKUP_2.slug,
    supervisor_version="2024.11.2",
    type=TEST_BACKUP_2.type,
)

TEST_BACKUP_3 = supervisor_backups.Backup(
    compressed=False,
    content=supervisor_backups.BackupContent(
        addons=["ssl"],
        folders=["share"],
        homeassistant=True,
    ),
    date=datetime.fromisoformat("1970-01-01T00:00:00Z"),
    location="share",
    location_attributes={
        LOCATION_LOCAL: supervisor_backups.BackupLocationAttributes(
            protected=False, size_bytes=1048576
        )
    },
    locations={"share"},
    name="Test",
    protected=False,
    size=1.0,
    size_bytes=1048576,
    slug="abc123",
    type=supervisor_backups.BackupType.PARTIAL,
)
TEST_BACKUP_DETAILS_3 = supervisor_backups.BackupComplete(
    addons=[
        supervisor_backups.BackupAddon(
            name="Terminal & SSH",
            size=0.0,
            slug="core_ssh",
            version="9.14.0",
        )
    ],
    compressed=TEST_BACKUP_3.compressed,
    date=TEST_BACKUP_3.date,
    extra=None,
    folders=["share"],
    homeassistant_exclude_database=False,
    homeassistant=None,
    location=TEST_BACKUP_3.location,
    location_attributes=TEST_BACKUP_3.location_attributes,
    locations=TEST_BACKUP_3.locations,
    name=TEST_BACKUP_3.name,
    protected=TEST_BACKUP_3.protected,
    repositories=[],
    size=TEST_BACKUP_3.size,
    size_bytes=TEST_BACKUP_3.size_bytes,
    slug=TEST_BACKUP_3.slug,
    supervisor_version="2024.11.2",
    type=TEST_BACKUP_3.type,
)


TEST_BACKUP_4 = supervisor_backups.Backup(
    compressed=False,
    content=supervisor_backups.BackupContent(
        addons=["ssl"],
        folders=["share"],
        homeassistant=True,
    ),
    date=datetime.fromisoformat("1970-01-01T00:00:00Z"),
    location=None,
    location_attributes={
        LOCATION_LOCAL: supervisor_backups.BackupLocationAttributes(
            protected=False, size_bytes=1048576
        )
    },
    locations={None},
    name="Test",
    protected=False,
    size=1.0,
    size_bytes=1048576,
    slug="abc123",
    type=supervisor_backups.BackupType.PARTIAL,
)
TEST_BACKUP_DETAILS_4 = supervisor_backups.BackupComplete(
    addons=[
        supervisor_backups.BackupAddon(
            name="Terminal & SSH",
            size=0.0,
            slug="core_ssh",
            version="9.14.0",
        )
    ],
    compressed=TEST_BACKUP.compressed,
    date=TEST_BACKUP.date,
    extra=None,
    folders=["share"],
    homeassistant_exclude_database=True,
    homeassistant="2024.12.0",
    location=TEST_BACKUP.location,
    location_attributes=TEST_BACKUP.location_attributes,
    locations=TEST_BACKUP.locations,
    name=TEST_BACKUP.name,
    protected=TEST_BACKUP.protected,
    repositories=[],
    size=TEST_BACKUP.size,
    size_bytes=TEST_BACKUP.size_bytes,
    slug=TEST_BACKUP.slug,
    supervisor_version="2024.11.2",
    type=TEST_BACKUP.type,
)

TEST_BACKUP_5 = supervisor_backups.Backup(
    compressed=False,
    content=supervisor_backups.BackupContent(
        addons=["ssl"],
        folders=[supervisor_backups.Folder.SHARE],
        homeassistant=True,
    ),
    date=datetime.fromisoformat("1970-01-01T00:00:00Z"),
    location=LOCATION_CLOUD_BACKUP,
    location_attributes={
        LOCATION_CLOUD_BACKUP: supervisor_backups.BackupLocationAttributes(
            protected=False, size_bytes=1048576
        )
    },
    locations={LOCATION_CLOUD_BACKUP},
    name="Test",
    protected=False,
    size=1.0,
    size_bytes=1048576,
    slug="abc123",
    type=supervisor_backups.BackupType.PARTIAL,
)
TEST_BACKUP_DETAILS_5 = supervisor_backups.BackupComplete(
    addons=[
        supervisor_backups.BackupAddon(
            name="Terminal & SSH",
            size=0.0,
            slug="core_ssh",
            version="9.14.0",
        )
    ],
    compressed=TEST_BACKUP_5.compressed,
    date=TEST_BACKUP_5.date,
    extra=None,
    folders=[supervisor_backups.Folder.SHARE],
    homeassistant_exclude_database=False,
    homeassistant="2024.12.0",
    location=TEST_BACKUP_5.location,
    location_attributes=TEST_BACKUP_5.location_attributes,
    locations=TEST_BACKUP_5.locations,
    name=TEST_BACKUP_5.name,
    protected=TEST_BACKUP_5.protected,
    repositories=[],
    size=TEST_BACKUP_5.size,
    size_bytes=TEST_BACKUP_5.size_bytes,
    slug=TEST_BACKUP_5.slug,
    supervisor_version="2024.11.2",
    type=TEST_BACKUP_5.type,
)

TEST_JOB_ID = "d17bd02be1f0437fa7264b16d38f700e"
TEST_JOB_NOT_DONE = supervisor_jobs.Job(
    name="backup_manager_partial_backup",
    reference="1ef41507",
    uuid=UUID(TEST_JOB_ID),
    progress=0.0,
    stage="copy_additional_locations",
    done=False,
    errors=[],
    child_jobs=[],
)
TEST_JOB_DONE = supervisor_jobs.Job(
    name="backup_manager_partial_backup",
    reference="1ef41507",
    uuid=UUID(TEST_JOB_ID),
    progress=0.0,
    stage="copy_additional_locations",
    done=True,
    errors=[],
    child_jobs=[],
)


@pytest.fixture(autouse=True)
def fixture_supervisor_environ() -> Generator[None]:
    """Mock os environ for supervisor."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        yield


@pytest.fixture(autouse=True)
async def hassio_enabled(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> AsyncGenerator[None]:
    """Enable hassio."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=True),
        patch("homeassistant.components.backup.backup.is_hassio", return_value=True),
    ):
        yield


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, hassio_enabled: None, supervisor_client: AsyncMock
) -> None:
    """Set up Backup integration."""
    assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
    await hass.async_block_till_done()


class BackupAgentTest(BackupAgent):
    """Test backup agent."""

    def __init__(self, name: str, domain: str = "test") -> None:
        """Initialize the backup agent."""
        self.domain = domain
        self.name = name
        self.unique_id = name

    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        return AsyncMock(spec_set=["__aiter__"])

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        await open_stream()

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return []

    async def async_get_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AgentBackup | None:
        """Return a backup."""
        return None

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup file."""


async def _setup_backup_platform(
    hass: HomeAssistant,
    *,
    domain: str,
    platform: BackupAgentPlatformProtocol,
) -> None:
    """Set up a mock domain."""
    mock_platform(hass, f"{domain}.backup", platform)
    assert await async_setup_component(hass, domain, {})
    await hass.async_block_till_done()


@pytest.mark.usefixtures("hassio_client")
@pytest.mark.parametrize(
    ("mounts", "expected_agents"),
    [
        (
            MountsInfo(default_backup_mount=None, mounts=[]),
            [BackupAgentTest("local", DOMAIN)],
        ),
        (
            MountsInfo(
                default_backup_mount=None,
                mounts=[
                    supervisor_mounts.CIFSMountResponse(
                        share="test",
                        name="test",
                        read_only=False,
                        state=supervisor_mounts.MountState.ACTIVE,
                        user_path="test",
                        usage=supervisor_mounts.MountUsage.BACKUP,
                        server="test",
                        type=supervisor_mounts.MountType.CIFS,
                    )
                ],
            ),
            [BackupAgentTest("local", DOMAIN), BackupAgentTest("test", DOMAIN)],
        ),
        (
            MountsInfo(
                default_backup_mount=None,
                mounts=[
                    supervisor_mounts.CIFSMountResponse(
                        share="test",
                        name="test",
                        read_only=False,
                        state=supervisor_mounts.MountState.ACTIVE,
                        user_path="test",
                        usage=supervisor_mounts.MountUsage.MEDIA,
                        server="test",
                        type=supervisor_mounts.MountType.CIFS,
                    )
                ],
            ),
            [BackupAgentTest("local", DOMAIN)],
        ),
    ],
)
async def test_agent_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    mounts: MountsInfo,
    expected_agents: list[BackupAgent],
) -> None:
    """Test backup agent info."""
    client = await hass_ws_client(hass)
    supervisor_client.mounts.info.return_value = mounts

    assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [
            {"agent_id": agent.agent_id, "name": agent.name}
            for agent in expected_agents
        ],
    }


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize(
    ("backup", "backup_details", "expected_response"),
    [
        (
            TEST_BACKUP,
            TEST_BACKUP_DETAILS,
            {
                "addons": [
                    {"name": "Terminal & SSH", "slug": "core_ssh", "version": "9.14.0"}
                ],
                "agents": {"hassio.local": {"protected": False, "size": 1048576}},
                "backup_id": "abc123",
                "database_included": True,
                "date": "1970-01-01T00:00:00+00:00",
                "failed_agent_ids": [],
                "folders": ["share"],
                "homeassistant_included": True,
                "homeassistant_version": "2024.12.0",
                "name": "Test",
                "with_automatic_settings": None,
            },
        ),
        (
            TEST_BACKUP_2,
            TEST_BACKUP_DETAILS_2,
            {
                "addons": [
                    {"name": "Terminal & SSH", "slug": "core_ssh", "version": "9.14.0"}
                ],
                "agents": {"hassio.local": {"protected": False, "size": 1048576}},
                "backup_id": "abc123",
                "database_included": False,
                "date": "1970-01-01T00:00:00+00:00",
                "failed_agent_ids": [],
                "folders": ["share"],
                "homeassistant_included": False,
                "homeassistant_version": None,
                "name": "Test",
                "with_automatic_settings": None,
            },
        ),
    ],
)
async def test_agent_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    backup: supervisor_backups.Backup,
    backup_details: supervisor_backups.BackupComplete,
    expected_response: dict[str, Any],
) -> None:
    """Test agent list backups."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.list.return_value = [backup, TEST_BACKUP_3]
    supervisor_client.backups.backup_info.return_value = backup_details

    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backups"] == [expected_response]


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_agent_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent download backup."""
    client = await hass_client()
    backup_id = "abc123"
    supervisor_client.backups.list.return_value = [TEST_BACKUP]
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS
    supervisor_client.backups.download_backup.return_value.__aiter__.return_value = (
        iter((b"backup data",))
    )

    resp = await client.get(f"/api/backup/download/{backup_id}?agent_id=hassio.local")
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"

    supervisor_client.backups.download_backup.assert_called_once_with(
        "abc123", options=supervisor_backups.DownloadBackupOptions(location=None)
    )


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_agent_download_unavailable_backup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent download backup which does not exist."""
    client = await hass_client()
    backup_id = "abc123"
    supervisor_client.backups.list.return_value = [TEST_BACKUP_3]
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS_3
    supervisor_client.backups.download_backup.return_value.__aiter__.return_value = (
        iter((b"backup data",))
    )

    resp = await client.get(f"/api/backup/download/{backup_id}?agent_id=hassio.local")
    assert resp.status == 404


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_agent_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    backup_id = "test-backup"
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS
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

    supervisor_client.backups.reload.assert_not_called()
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.open"),
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("shutil.copy"),
    ):
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=hassio.local",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    supervisor_client.backups.reload.assert_not_called()
    supervisor_client.backups.download_backup.assert_not_called()
    supervisor_client.backups.remove_backup.assert_not_called()


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_agent_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent get backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS
    backup_id = "abc123"

    await client.send_json_auto_id(
        {
            "type": "backup/details",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_errors": {},
        "backup": {
            "addons": [
                {"name": "Terminal & SSH", "slug": "core_ssh", "version": "9.14.0"}
            ],
            "agents": {"hassio.local": {"protected": False, "size": 1048576}},
            "backup_id": "abc123",
            "database_included": True,
            "date": "1970-01-01T00:00:00+00:00",
            "failed_agent_ids": [],
            "folders": ["share"],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Test",
            "with_automatic_settings": None,
        },
    }
    supervisor_client.backups.backup_info.assert_called_once_with(backup_id)


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize(
    ("backup_info_side_effect", "expected_response"),
    [
        (
            SupervisorBadRequestError("blah"),
            {
                "success": False,
                "error": {"code": "unknown_error", "message": "Unknown error"},
            },
        ),
        (
            SupervisorNotFoundError(),
            {
                "success": True,
                "result": {"agent_errors": {}, "backup": None},
            },
        ),
    ],
)
async def test_agent_get_backup_with_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    backup_info_side_effect: Exception,
    expected_response: dict[str, Any],
) -> None:
    """Test agent get backup."""
    client = await hass_ws_client(hass)
    backup_id = "abc123"

    supervisor_client.backups.backup_info.side_effect = backup_info_side_effect
    await client.send_json_auto_id(
        {
            "type": "backup/details",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response == {"id": 1, "type": "result"} | expected_response
    supervisor_client.backups.backup_info.assert_called_once_with(backup_id)


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_agent_delete_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent delete backup."""
    client = await hass_ws_client(hass)
    backup_id = "abc123"

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    supervisor_client.backups.remove_backup.assert_called_once_with(
        backup_id, options=supervisor_backups.RemoveBackupOptions(location={None})
    )


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize(
    ("remove_side_effect", "expected_response"),
    [
        (
            SupervisorBadRequestError("blah"),
            {
                "success": False,
                "error": {"code": "unknown_error", "message": "Unknown error"},
            },
        ),
        (
            SupervisorNotFoundError(),
            {
                "success": True,
                "result": {"agent_errors": {}},
            },
        ),
    ],
)
async def test_agent_delete_with_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    remove_side_effect: Exception,
    expected_response: dict[str, Any],
) -> None:
    """Test agent delete backup."""
    client = await hass_ws_client(hass)
    backup_id = "abc123"

    supervisor_client.backups.remove_backup.side_effect = remove_side_effect
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response == {"id": 1, "type": "result"} | expected_response
    supervisor_client.backups.remove_backup.assert_called_once_with(
        backup_id, options=supervisor_backups.RemoveBackupOptions(location={None})
    )


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize(
    ("event_data", "mount_info_calls"),
    [
        (
            {
                "event": "job",
                "data": {"name": "mount_manager_create_mount", "done": True},
            },
            1,
        ),
        (
            {
                "event": "job",
                "data": {"name": "mount_manager_create_mount", "done": False},
            },
            0,
        ),
        (
            {
                "event": "job",
                "data": {"name": "mount_manager_remove_mount", "done": True},
            },
            1,
        ),
        (
            {
                "event": "job",
                "data": {"name": "mount_manager_remove_mount", "done": False},
            },
            0,
        ),
        ({"event": "job", "data": {"name": "other_job", "done": True}}, 0),
        (
            {
                "event": "other_event",
                "data": {"name": "mount_manager_remove_mount", "done": True},
            },
            0,
        ),
    ],
)
async def test_agents_notify_on_mount_added_removed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    event_data: dict[str, Any],
    mount_info_calls: int,
) -> None:
    """Test the listener is called when mounts are added or removed."""
    client = await hass_ws_client(hass)
    assert supervisor_client.mounts.info.call_count == 1
    assert supervisor_client.mounts.info.call_args[0] == ()
    supervisor_client.mounts.info.reset_mock()

    await client.send_json_auto_id({"type": "supervisor/event", "data": event_data})
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    assert supervisor_client.mounts.info.call_count == mount_info_calls


DEFAULT_BACKUP_OPTIONS = supervisor_backups.PartialBackupOptions(
    addons=None,
    background=True,
    compressed=True,
    extra={
        "instance_id": ANY,
        "supervisor.backup_request_date": "2025-01-30T05:42:12.345678-08:00",
        "with_automatic_settings": False,
    },
    filename=PurePath("Test_-_2025-01-30_05.42_12345678.tar"),
    folders={"ssl"},
    homeassistant_exclude_database=False,
    homeassistant=True,
    location=[None],
    name="Test",
    password=None,
)


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize(
    ("extra_generate_options", "expected_supervisor_options"),
    [
        (
            {},
            DEFAULT_BACKUP_OPTIONS,
        ),
        (
            {"include_addons": ["addon_1", "addon_2"]},
            replace(DEFAULT_BACKUP_OPTIONS, addons={"addon_1", "addon_2"}),
        ),
        (
            {"include_all_addons": True},
            replace(DEFAULT_BACKUP_OPTIONS, addons="ALL"),
        ),
        (
            {"include_database": False},
            replace(DEFAULT_BACKUP_OPTIONS, homeassistant_exclude_database=True),
        ),
        (
            {"include_folders": ["media", "share"]},
            replace(DEFAULT_BACKUP_OPTIONS, folders={"media", "share", "ssl"}),
        ),
        (
            {
                "include_folders": ["media"],
                "include_database": False,
                "include_homeassistant": False,
            },
            replace(
                DEFAULT_BACKUP_OPTIONS,
                folders={"media"},
                homeassistant=False,
                homeassistant_exclude_database=True,
            ),
        ),
    ],
)
async def test_reader_writer_create(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    extra_generate_options: dict[str, Any],
    expected_supervisor_options: supervisor_backups.PartialBackupOptions,
) -> None:
    """Test generating a backup."""
    client = await hass_ws_client(hass)
    freezer.move_to("2025-01-30 13:42:12.345678")
    supervisor_client.backups.partial_backup.return_value.job_id = TEST_JOB_ID
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS
    supervisor_client.jobs.get_job.return_value = TEST_JOB_NOT_DONE

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["hassio.local"], "name": "Test"}
        | extra_generate_options
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"backup_job_id": TEST_JOB_ID}

    supervisor_client.backups.partial_backup.assert_called_once_with(
        expected_supervisor_options
    )

    await client.send_json_auto_id(
        {
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {"done": True, "uuid": TEST_JOB_ID, "reference": "test_slug"},
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": "upload_to_agents",
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "completed",
    }

    supervisor_client.backups.download_backup.assert_not_called()
    supervisor_client.backups.remove_backup.assert_not_called()

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_reader_writer_create_job_done(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test generating a backup, and backup job finishes early."""
    client = await hass_ws_client(hass)
    freezer.move_to("2025-01-30 13:42:12.345678")
    supervisor_client.backups.partial_backup.return_value.job_id = TEST_JOB_ID
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS
    supervisor_client.jobs.get_job.return_value = TEST_JOB_DONE

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["hassio.local"], "name": "Test"}
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"backup_job_id": TEST_JOB_ID}

    supervisor_client.backups.partial_backup.assert_called_once_with(
        DEFAULT_BACKUP_OPTIONS
    )

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": "upload_to_agents",
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "completed",
    }

    supervisor_client.backups.download_backup.assert_not_called()
    supervisor_client.backups.remove_backup.assert_not_called()

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}


@pytest.mark.usefixtures("hassio_client")
@pytest.mark.parametrize(
    (
        "commands",
        "password",
        "agent_ids",
        "password_sent_to_supervisor",
        "create_locations",
        "create_protected",
        "upload_locations",
    ),
    [
        (
            [],
            None,
            ["hassio.local", "hassio.share1", "hassio.share2", "hassio.share3"],
            None,
            [None, "share1", "share2", "share3"],
            False,
            [],
        ),
        (
            [],
            "hunter2",
            ["hassio.local", "hassio.share1", "hassio.share2", "hassio.share3"],
            "hunter2",
            [None, "share1", "share2", "share3"],
            True,
            [],
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "hassio.local": {"protected": False},
                    },
                }
            ],
            "hunter2",
            ["hassio.local", "hassio.share1", "hassio.share2", "hassio.share3"],
            "hunter2",
            ["share1", "share2", "share3"],
            True,
            [None],
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "hassio.local": {"protected": False},
                        "hassio.share1": {"protected": False},
                    },
                }
            ],
            "hunter2",
            ["hassio.local", "hassio.share1", "hassio.share2", "hassio.share3"],
            "hunter2",
            ["share2", "share3"],
            True,
            [None, "share1"],
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "hassio.local": {"protected": False},
                        "hassio.share1": {"protected": False},
                        "hassio.share2": {"protected": False},
                    },
                }
            ],
            "hunter2",
            ["hassio.local", "hassio.share1", "hassio.share2", "hassio.share3"],
            None,
            [None, "share1", "share2"],
            True,
            ["share3"],
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "agents": {
                        "hassio.local": {"protected": False},
                    },
                }
            ],
            "hunter2",
            ["hassio.local"],
            None,
            [None],
            False,
            [],
        ),
    ],
)
async def test_reader_writer_create_per_agent_encryption(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    commands: dict[str, Any],
    password: str | None,
    agent_ids: list[str],
    password_sent_to_supervisor: str | None,
    create_locations: list[str | None],
    create_protected: bool,
    upload_locations: list[str | None],
) -> None:
    """Test generating a backup."""
    client = await hass_ws_client(hass)
    freezer.move_to("2025-01-30 13:42:12.345678")
    mounts = MountsInfo(
        default_backup_mount=None,
        mounts=[
            supervisor_mounts.CIFSMountResponse(
                share=f"share{i}",
                name=f"share{i}",
                read_only=False,
                state=supervisor_mounts.MountState.ACTIVE,
                user_path=f"share{i}",
                usage=supervisor_mounts.MountUsage.BACKUP,
                server=f"share{i}",
                type=supervisor_mounts.MountType.CIFS,
            )
            for i in range(1, 4)
        ],
    )
    supervisor_client.backups.partial_backup.return_value.job_id = TEST_JOB_ID
    supervisor_client.backups.backup_info.return_value = replace(
        TEST_BACKUP_DETAILS,
        extra=DEFAULT_BACKUP_OPTIONS.extra,
        locations=create_locations,
        location_attributes={
            location or LOCATION_LOCAL: supervisor_backups.BackupLocationAttributes(
                protected=create_protected,
                size_bytes=TEST_BACKUP_DETAILS.size_bytes,
            )
            for location in create_locations
        },
    )
    supervisor_client.jobs.get_job.return_value = TEST_JOB_NOT_DONE
    supervisor_client.mounts.info.return_value = mounts
    assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})

    for command in commands:
        await client.send_json_auto_id(command)
        result = await client.receive_json()
        assert result["success"] is True

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {
            "type": "backup/generate",
            "agent_ids": agent_ids,
            "name": "Test",
            "password": password,
        }
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"backup_job_id": TEST_JOB_ID}

    supervisor_client.backups.partial_backup.assert_called_once_with(
        replace(
            DEFAULT_BACKUP_OPTIONS,
            password=password_sent_to_supervisor,
            location=create_locations,
        )
    )

    await client.send_json_auto_id(
        {
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {"done": True, "uuid": TEST_JOB_ID, "reference": "test_slug"},
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": "upload_to_agents",
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "completed",
    }

    assert len(supervisor_client.backups.upload_backup.mock_calls) == len(
        upload_locations
    )
    for call in supervisor_client.backups.upload_backup.mock_calls:
        assert call.args[1].filename == PurePath("Test_-_2025-01-30_05.42_12345678.tar")
        upload_call_locations: set = call.args[1].location
        assert len(upload_call_locations) == 1
        assert upload_call_locations.pop() in upload_locations
    supervisor_client.backups.remove_backup.assert_not_called()

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize(
    ("side_effect", "error_code", "error_message", "expected_reason"),
    [
        (
            SupervisorError("Boom!"),
            "home_assistant_error",
            "Error creating backup: Boom!",
            "backup_manager_error",
        ),
        (
            Exception("Boom!"),
            "unknown_error",
            "Unknown error",
            "unknown_error",
        ),
    ],
)
async def test_reader_writer_create_partial_backup_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    side_effect: Exception,
    error_code: str,
    error_message: str,
    expected_reason: str,
) -> None:
    """Test client partial backup error when generating a backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.partial_backup.side_effect = side_effect

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["hassio.local"], "name": "Test"}
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": expected_reason,
        "stage": None,
        "state": "failed",
    }

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}

    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == error_code
    assert response["error"]["message"] == error_message

    assert supervisor_client.backups.partial_backup.call_count == 1


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_reader_writer_create_missing_reference_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test missing reference error when generating a backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.partial_backup.return_value.job_id = TEST_JOB_ID
    supervisor_client.jobs.get_job.return_value = TEST_JOB_NOT_DONE

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["hassio.local"], "name": "Test"}
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"backup_job_id": TEST_JOB_ID}

    assert supervisor_client.backups.partial_backup.call_count == 1

    await client.send_json_auto_id(
        {
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {"done": True, "uuid": TEST_JOB_ID},
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": "upload_failed",
        "stage": None,
        "state": "failed",
    }

    await hass.async_block_till_done()

    assert supervisor_client.backups.backup_info.call_count == 0
    assert supervisor_client.backups.download_backup.call_count == 0
    assert supervisor_client.backups.remove_backup.call_count == 0

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize("exception", [SupervisorError("Boom!"), Exception("Boom!")])
@pytest.mark.parametrize(
    ("method", "download_call_count", "remove_call_count"),
    [("download_backup", 1, 1), ("remove_backup", 1, 1)],
)
async def test_reader_writer_create_download_remove_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    exception: Exception,
    method: str,
    download_call_count: int,
    remove_call_count: int,
) -> None:
    """Test download and remove error when generating a backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.partial_backup.return_value.job_id = TEST_JOB_ID
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS_5
    supervisor_client.jobs.get_job.return_value = TEST_JOB_NOT_DONE
    method_mock = getattr(supervisor_client.backups, method)
    method_mock.side_effect = exception

    remote_agent = BackupAgentTest("remote")
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
            spec_set=BackupAgentPlatformProtocol,
        ),
    )

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["test.remote"], "name": "Test"}
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"backup_job_id": TEST_JOB_ID}

    assert supervisor_client.backups.partial_backup.call_count == 1

    await client.send_json_auto_id(
        {
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {"done": True, "uuid": TEST_JOB_ID, "reference": "test_slug"},
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": "upload_to_agents",
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": "upload_failed",
        "stage": None,
        "state": "failed",
    }

    await hass.async_block_till_done()

    assert supervisor_client.backups.backup_info.call_count == 1
    assert supervisor_client.backups.download_backup.call_count == download_call_count
    assert supervisor_client.backups.remove_backup.call_count == remove_call_count

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize("exception", [SupervisorError("Boom!"), Exception("Boom!")])
async def test_reader_writer_create_info_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test backup info error when generating a backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.partial_backup.return_value.job_id = TEST_JOB_ID
    supervisor_client.backups.backup_info.side_effect = exception
    supervisor_client.jobs.get_job.return_value = TEST_JOB_NOT_DONE

    remote_agent = BackupAgentTest("remote")
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
            spec_set=BackupAgentPlatformProtocol,
        ),
    )

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["test.remote"], "name": "Test"}
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"backup_job_id": TEST_JOB_ID}

    assert supervisor_client.backups.partial_backup.call_count == 1

    await client.send_json_auto_id(
        {
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {"done": True, "uuid": TEST_JOB_ID, "reference": "test_slug"},
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": "upload_failed",
        "stage": None,
        "state": "failed",
    }

    await hass.async_block_till_done()

    assert supervisor_client.backups.backup_info.call_count == 1
    assert supervisor_client.backups.download_backup.call_count == 0
    assert supervisor_client.backups.remove_backup.call_count == 0

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_reader_writer_create_remote_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test generating a backup which will be uploaded to a remote agent."""
    client = await hass_ws_client(hass)
    freezer.move_to("2025-01-30 13:42:12.345678")
    supervisor_client.backups.partial_backup.return_value.job_id = TEST_JOB_ID
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS_5
    supervisor_client.jobs.get_job.return_value = TEST_JOB_NOT_DONE

    remote_agent = BackupAgentTest("remote")
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
            spec_set=BackupAgentPlatformProtocol,
        ),
    )

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["test.remote"], "name": "Test"}
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"backup_job_id": TEST_JOB_ID}

    supervisor_client.backups.partial_backup.assert_called_once_with(
        replace(DEFAULT_BACKUP_OPTIONS, location=[LOCATION_CLOUD_BACKUP]),
    )

    await client.send_json_auto_id(
        {
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {"done": True, "uuid": TEST_JOB_ID, "reference": "test_slug"},
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": "upload_to_agents",
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "completed",
    }

    supervisor_client.backups.download_backup.assert_called_once_with("test_slug")
    supervisor_client.backups.remove_backup.assert_called_once_with(
        "test_slug",
        options=supervisor_backups.RemoveBackupOptions({LOCATION_CLOUD_BACKUP}),
    )


@pytest.mark.usefixtures("hassio_client", "setup_integration")
@pytest.mark.parametrize(
    ("extra_generate_options", "expected_error"),
    [
        (
            {"include_homeassistant": False},
            {
                "code": "home_assistant_error",
                "message": "Cannot create a backup with database but without Home Assistant",
            },
        ),
        (
            {"include_homeassistant": False, "include_database": False},
            {
                "code": "unknown_error",
                "message": "Unknown error",
            },
        ),
    ],
)
async def test_reader_writer_create_wrong_parameters(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    extra_generate_options: dict[str, Any],
    expected_error: dict[str, str],
) -> None:
    """Test generating a backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.partial_backup.return_value.job_id = TEST_JOB_ID
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["hassio.local"], "name": "Test"}
        | extra_generate_options
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "create_backup",
        "reason": "unknown_error",
        "stage": None,
        "state": "failed",
    }

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "idle",
    }

    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == expected_error

    supervisor_client.backups.partial_backup.assert_not_called()


@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_agent_receive_remote_backup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test receiving a backup which will be uploaded to a remote agent."""
    client = await hass_client()
    backup_id = "test-backup"
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS_5
    supervisor_client.backups.upload_backup.return_value = "test_slug"
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
        size=0.0,
    )

    remote_agent = BackupAgentTest("remote")
    await _setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=AsyncMock(return_value=[remote_agent]),
            spec_set=BackupAgentPlatformProtocol,
        ),
    )

    supervisor_client.backups.reload.assert_not_called()
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.open"),
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("shutil.copy"),
    ):
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=test.remote",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201

    supervisor_client.backups.download_backup.assert_called_once_with("test_slug")
    supervisor_client.backups.remove_backup.assert_called_once_with(
        "test_slug",
        options=supervisor_backups.RemoveBackupOptions({LOCATION_CLOUD_BACKUP}),
    )


@pytest.mark.parametrize(
    ("get_job_result", "supervisor_events"),
    [
        (
            TEST_JOB_NOT_DONE,
            [{"event": "job", "data": {"done": True, "uuid": TEST_JOB_ID}}],
        ),
        (
            TEST_JOB_DONE,
            [],
        ),
    ],
)
@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_reader_writer_restore(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    get_job_result: supervisor_jobs.Job,
    supervisor_events: list[dict[str, Any]],
) -> None:
    """Test restoring a backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.partial_restore.return_value.job_id = TEST_JOB_ID
    supervisor_client.backups.list.return_value = [TEST_BACKUP]
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS
    supervisor_client.jobs.get_job.return_value = get_job_result

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "idle",
    }
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/restore", "agent_id": "hassio.local", "backup_id": "abc123"}
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "restore_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    supervisor_client.backups.partial_restore.assert_called_once_with(
        "abc123",
        supervisor_backups.PartialRestoreOptions(
            addons=None,
            background=True,
            folders=None,
            homeassistant=True,
            location=None,
            password=None,
        ),
    )

    for event in supervisor_events:
        await client.send_json_auto_id({"type": "supervisor/event", "data": event})
        response = await client.receive_json()
        assert response["success"]

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "restore_backup",
        "reason": None,
        "stage": None,
        "state": "completed",
    }

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}

    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None


@pytest.mark.parametrize(
    ("supervisor_error_string", "expected_error_code", "expected_reason"),
    [
        ("Invalid password for backup", "password_incorrect", "password_incorrect"),
        (
            "Backup was made on supervisor version 2025.12.0, can't restore on 2024.12.0. Must update supervisor first.",
            "home_assistant_error",
            "unknown_error",
        ),
    ],
)
@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_reader_writer_restore_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    supervisor_error_string: str,
    expected_error_code: str,
    expected_reason: str,
) -> None:
    """Test restoring a backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.partial_restore.side_effect = SupervisorBadRequestError(
        supervisor_error_string
    )
    supervisor_client.backups.list.return_value = [TEST_BACKUP]
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS

    await client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "backup/restore", "agent_id": "hassio.local", "backup_id": "abc123"}
    )
    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "restore_backup",
        "reason": None,
        "stage": None,
        "state": "in_progress",
    }

    supervisor_client.backups.partial_restore.assert_called_once_with(
        "abc123",
        supervisor_backups.PartialRestoreOptions(
            addons=None,
            background=True,
            folders=None,
            homeassistant=True,
            location=None,
            password=None,
        ),
    )

    response = await client.receive_json()
    assert response["event"] == {
        "manager_state": "restore_backup",
        "reason": expected_reason,
        "stage": None,
        "state": "failed",
    }

    response = await client.receive_json()
    assert response["event"] == {"manager_state": "idle"}

    response = await client.receive_json()
    assert response["error"]["code"] == expected_error_code


@pytest.mark.parametrize(
    ("backup", "backup_details", "parameters", "expected_error"),
    [
        (
            TEST_BACKUP,
            TEST_BACKUP_DETAILS,
            {"restore_database": False},
            "Restore database must match backup",
        ),
        (
            TEST_BACKUP,
            TEST_BACKUP_DETAILS,
            {"restore_homeassistant": False},
            "Cannot restore database without Home Assistant",
        ),
        (
            TEST_BACKUP_4,
            TEST_BACKUP_DETAILS_4,
            {"restore_homeassistant": True, "restore_database": True},
            "Restore database must match backup",
        ),
    ],
)
@pytest.mark.usefixtures("hassio_client", "setup_integration")
async def test_reader_writer_restore_wrong_parameters(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    backup: supervisor_backups.Backup,
    backup_details: supervisor_backups.BackupComplete,
    parameters: dict[str, Any],
    expected_error: str,
) -> None:
    """Test trigger restore."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.list.return_value = [backup]
    supervisor_client.backups.backup_info.return_value = backup_details

    default_parameters = {
        "type": "backup/restore",
        "agent_id": "hassio.local",
        "backup_id": "abc123",
    }

    await client.send_json_auto_id(default_parameters | parameters)
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": expected_error,
    }


@pytest.mark.usefixtures("hassio_client")
async def test_restore_progress_after_restart(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test restore backup progress after restart."""

    supervisor_client.jobs.get_job.return_value = TEST_JOB_DONE

    with patch.dict(os.environ, MOCK_ENVIRON | {RESTORE_JOB_ID_ENV: TEST_JOB_ID}):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["last_non_idle_event"] == {
        "manager_state": "restore_backup",
        "reason": "",
        "stage": None,
        "state": "completed",
    }
    assert response["result"]["state"] == "idle"


@pytest.mark.usefixtures("hassio_client")
async def test_restore_progress_after_restart_unknown_job(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test restore backup progress after restart."""

    supervisor_client.jobs.get_job.side_effect = SupervisorError

    with patch.dict(os.environ, MOCK_ENVIRON | {RESTORE_JOB_ID_ENV: TEST_JOB_ID}):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["last_non_idle_event"] is None
    assert response["result"]["state"] == "idle"
