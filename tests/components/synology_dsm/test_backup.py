"""Tests for the Synology DSM backup agent."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from synology_dsm.api.file_station.models import SynoFileFile, SynoFileSharedFolder

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN
from homeassistant.components.synology_dsm.const import (
    CONF_BACKUP_PATH,
    CONF_BACKUP_SHARE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.aiohttp import MockStreamReader

from .consts import HOST, MACS, PASSWORD, PORT, SERIAL, USE_SSL, USERNAME

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


class MockStreamReaderChunked(MockStreamReader):
    """Mock a stream reader with simulated chunked data."""

    async def readchunk(self) -> tuple[bytes, bool]:
        """Read bytes."""
        return (self._content.read(), False)


async def _mock_download_file(path: str, filename: str) -> MockStreamReader:
    if filename == "abcd12ef_meta.json":
        return MockStreamReader(
            b'{"addons":[],"backup_id":"abcd12ef","date":"2025-01-09T20:14:35.457323+01:00",'
            b'"database_included":true,"extra_metadata":{"instance_id":"36b3b7e984da43fc89f7bafb2645fa36",'
            b'"with_automatic_settings":true},"folders":[],"homeassistant_included":true,'
            b'"homeassistant_version":"2025.2.0.dev0","name":"Automatic backup 2025.2.0.dev0","protected":true,"size":13916160}'
        )
    if filename == "abcd12ef.tar":
        return MockStreamReaderChunked(b"backup data")
    return MockStreamReader(b"")


@pytest.fixture
def dsm_with_filestation():
    """Mock a successful service with filestation support."""

    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.utilisation = Mock(cpu_user_load=1, update=AsyncMock(return_value=True))
        dsm.network = Mock(update=AsyncMock(return_value=True), macs=MACS)
        dsm.storage = Mock(
            disks_ids=["sda", "sdb", "sdc"],
            volumes_ids=["volume_1"],
            update=AsyncMock(return_value=True),
        )
        dsm.information = Mock(serial=SERIAL)
        dsm.file = AsyncMock(
            get_shared_folders=AsyncMock(
                return_value=[
                    SynoFileSharedFolder(
                        additional=None,
                        is_dir=True,
                        name="HA Backup",
                        path="/ha_backup",
                    )
                ]
            ),
            get_files=AsyncMock(
                return_value=[
                    SynoFileFile(
                        additional=None,
                        is_dir=False,
                        name="abcd12ef_meta.json",
                        path="/ha_backup/my_backup_path/abcd12ef_meta.json",
                    ),
                    SynoFileFile(
                        additional=None,
                        is_dir=False,
                        name="abcd12ef.tar",
                        path="/ha_backup/my_backup_path/abcd12ef.tar",
                    ),
                ]
            ),
            download_file=_mock_download_file,
        )

        yield dsm


@pytest.fixture
async def setup_dsm_with_filestation(
    hass: HomeAssistant,
    dsm_with_filestation: MagicMock,
):
    """Mock setup of synology dsm config entry."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_filestation,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
                CONF_BACKUP_PATH: "my_backup_path",
                CONF_BACKUP_SHARE: "/ha_backup",
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
        await hass.async_block_till_done()

        yield entry


async def test_agents_info(
    hass: HomeAssistant,
    setup_dsm_with_filestation: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup agent info."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [
            {"agent_id": "synology_dsm.Mock Title"},
            {"agent_id": "backup.local"},
        ],
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    setup_dsm_with_filestation: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test agent list backups."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        {
            "addons": [],
            "backup_id": "abcd12ef",
            "date": "2025-01-09T20:14:35.457323+01:00",
            "database_included": True,
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2025.2.0.dev0",
            "name": "Automatic backup 2025.2.0.dev0",
            "protected": True,
            "size": 13916160,
            "agent_ids": ["synology_dsm.Mock Title"],
            "failed_agent_ids": [],
            "with_automatic_settings": None,
        }
    ]


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (
            "abcd12ef",
            {
                "addons": [],
                "backup_id": "abcd12ef",
                "date": "2025-01-09T20:14:35.457323+01:00",
                "database_included": True,
                "folders": [],
                "homeassistant_included": True,
                "homeassistant_version": "2025.2.0.dev0",
                "name": "Automatic backup 2025.2.0.dev0",
                "protected": True,
                "size": 13916160,
                "agent_ids": ["synology_dsm.Mock Title"],
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
    setup_dsm_with_filestation: MockConfigEntry,
    backup_id: str,
    expected_result: dict[str, Any] | None,
) -> None:
    """Test agent get backup."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == expected_result


async def test_agents_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_dsm_with_filestation: MockConfigEntry,
) -> None:
    """Test agent download backup."""
    client = await hass_client()
    backup_id = "abcd12ef"

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id=synology_dsm.Mock Title"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"
