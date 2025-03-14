"""Test repairs for synology dsm."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from synology_dsm.api.file_station.models import SynoFileSharedFolder

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
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
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .common import mock_dsm_information
from .consts import HOST, MACS, PASSWORD, PORT, USE_SSL, USERNAME

from tests.common import ANY, MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture
def mock_dsm_with_filestation():
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
        dsm.information = mock_dsm_information()
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
        )
        dsm.logout = AsyncMock(return_value=True)
        yield dsm


@pytest.fixture
async def setup_dsm_with_filestation(
    hass: HomeAssistant,
    mock_dsm_with_filestation: MagicMock,
):
    """Mock setup of synology dsm config entry."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=mock_dsm_with_filestation,
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
            },
            options={
                CONF_BACKUP_PATH: None,
                CONF_BACKUP_SHARE: None,
            },
            unique_id="my_serial",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert await async_setup_component(hass, REPAIRS_DOMAIN, {})
        await hass.async_block_till_done()

        yield mock_dsm_with_filestation


async def test_create_issue(
    hass: HomeAssistant,
    setup_dsm_with_filestation: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the issue is created."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["breaks_in_ha_version"] is None
    assert issue["domain"] == DOMAIN
    assert issue["issue_id"] == "missing_backup_setup_my_serial"
    assert issue["translation_key"] == "missing_backup_setup"


async def test_missing_backup_ignore(
    hass: HomeAssistant,
    setup_dsm_with_filestation: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test missing backup location setup issue is ignored by the user."""
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    # get repair issues
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert not issue["ignored"]

    # start repair flow
    data = await start_repair_fix_flow(client, DOMAIN, "missing_backup_setup_my_serial")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "docs_url": "https://www.home-assistant.io/integrations/synology_dsm/#backup-location"
    }
    assert data["step_id"] == "init"
    assert data["menu_options"] == ["confirm", "ignore"]

    # seelct to ignore the flow
    data = await process_repair_fix_flow(
        client, flow_id, json={"next_step_id": "ignore"}
    )
    assert data["type"] == "abort"
    assert data["reason"] == "ignored"

    # check issue is ignored
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["ignored"]


async def test_missing_backup_success(
    hass: HomeAssistant,
    setup_dsm_with_filestation: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the missing backup location setup repair flow is fully processed by the user."""
    ws_client = await hass_ws_client(hass)
    client = await hass_client()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.options == {"backup_path": None, "backup_share": None}

    # get repair issues
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert not issue["ignored"]

    # start repair flow
    data = await start_repair_fix_flow(client, DOMAIN, "missing_backup_setup_my_serial")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "docs_url": "https://www.home-assistant.io/integrations/synology_dsm/#backup-location"
    }
    assert data["step_id"] == "init"
    assert data["menu_options"] == ["confirm", "ignore"]

    # seelct to confirm the flow
    data = await process_repair_fix_flow(
        client, flow_id, json={"next_step_id": "confirm"}
    )
    assert data["step_id"] == "confirm"
    assert data["type"] == "form"

    # fill out the form and submit
    data = await process_repair_fix_flow(
        client,
        flow_id,
        json={"backup_share": "/ha_backup", "backup_path": "backup_ha_dev"},
    )
    assert data["type"] == "create_entry"
    assert entry.options == {
        "backup_path": "backup_ha_dev",
        "backup_share": "/ha_backup",
    }


async def test_missing_backup_no_shares(
    hass: HomeAssistant,
    setup_dsm_with_filestation: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the missing backup location setup repair flow errors out."""
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    # get repair issues
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1

    # start repair flow
    data = await start_repair_fix_flow(client, DOMAIN, "missing_backup_setup_my_serial")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "docs_url": "https://www.home-assistant.io/integrations/synology_dsm/#backup-location"
    }
    assert data["step_id"] == "init"
    assert data["menu_options"] == ["confirm", "ignore"]

    # inject error
    setup_dsm_with_filestation.file.get_shared_folders.return_value = []

    # select to confirm the flow
    data = await process_repair_fix_flow(
        client, flow_id, json={"next_step_id": "confirm"}
    )
    assert data["type"] == "abort"
    assert data["reason"] == "no_shares"


@pytest.mark.parametrize(
    "ignore_missing_translations",
    ["component.synology_dsm.issues.other_issue.title"],
)
async def test_other_fixable_issues(
    hass: HomeAssistant,
    setup_dsm_with_filestation: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing another issue."""
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    issue = {
        "breaks_in_ha_version": None,
        "domain": DOMAIN,
        "issue_id": "other_issue",
        "is_fixable": True,
        "severity": "error",
        "translation_key": "other_issue",
    }
    ir.async_create_issue(
        hass,
        issue["domain"],
        issue["issue_id"],
        is_fixable=issue["is_fixable"],
        severity=issue["severity"],
        translation_key=issue["translation_key"],
    )

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    results = msg["result"]["issues"]
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "synology_dsm",
        "ignored": False,
        "is_fixable": True,
        "issue_domain": None,
        "issue_id": "other_issue",
        "learn_more_url": None,
        "severity": "error",
        "translation_key": "other_issue",
        "translation_placeholders": None,
    } in results

    data = await start_repair_fix_flow(client, DOMAIN, "other_issue")

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()
