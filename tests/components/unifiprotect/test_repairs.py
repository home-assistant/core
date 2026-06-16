"""Test repairs for unifiprotect."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from uiprotect.data import Camera, CloudAccount, Version

from homeassistant.components.unifiprotect.const import (
    CONF_DISABLE_RTSP,
    CONF_USE_PUBLIC_API_STREAMS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .utils import MockUFPFixture, init_entry

from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(name="ufp_options")
def _private_stream_options() -> dict[str, bool]:
    """The RTSP repair belongs to the legacy private stream path."""
    return {CONF_USE_PUBLIC_API_STREAMS: False}


async def test_cloud_user_fix(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    cloud_account: CloudAccount,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test EA warning is created if using prerelease version of Protect."""

    ufp.api.bootstrap.nvr.version = Version("2.2.6")
    user = ufp.api.bootstrap.users[ufp.api.bootstrap.auth_user_id]
    user.cloud_account = cloud_account
    ufp.api.bootstrap.users[ufp.api.bootstrap.auth_user_id] = user
    await init_entry(hass, ufp, [])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "cloud_user":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "cloud_user")

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()
    assert any(ufp.entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_rtsp_read_only_ignore(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test RTSP disabled warning if camera is read-only and it is ignored."""

    for channel in doorbell.channels:
        channel.is_rtsp_enabled = False
    for user in ufp.api.bootstrap.users.values():
        user.all_permissions = []

    ufp.api.get_camera = AsyncMock(return_value=doorbell)
    ufp.api.create_camera_rtsps_streams = AsyncMock(return_value=None)

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issue_id = f"rtsp_disabled_{doorbell.id}"

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == issue_id:
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, flow_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"


async def test_rtsp_read_only_fix(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test RTSP disabled warning if camera is read-only and it is fixed."""

    for channel in doorbell.channels:
        channel.is_rtsp_enabled = False
    for user in ufp.api.bootstrap.users.values():
        user.all_permissions = []

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    new_doorbell = deepcopy(doorbell)
    new_doorbell.channels[1].is_rtsp_enabled = True
    ufp.api.get_camera = AsyncMock(return_value=new_doorbell)
    ufp.api.create_camera_rtsps_streams = AsyncMock(return_value=None)
    issue_id = f"rtsp_disabled_{doorbell.id}"

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == issue_id:
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"


async def test_rtsp_writable_fix(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test RTSP disabled warning if camera is writable and it is ignored."""

    for channel in doorbell.channels:
        channel.is_rtsp_enabled = False

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    new_doorbell = deepcopy(doorbell)
    new_doorbell.channels[0].is_rtsp_enabled = True

    ufp.api.get_camera = AsyncMock(side_effect=[doorbell, new_doorbell])
    ufp.api.create_camera_rtsps_streams = AsyncMock(return_value=None)
    issue_id = f"rtsp_disabled_{doorbell.id}"

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == issue_id:
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"

    ufp.api.create_camera_rtsps_streams.assert_called_with(doorbell.id, "high")


async def test_rtsp_writable_fix_when_not_setup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test RTSP disabled warning if the integration is no longer set up."""

    for channel in doorbell.channels:
        channel.is_rtsp_enabled = False

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    new_doorbell = deepcopy(doorbell)
    new_doorbell.channels[0].is_rtsp_enabled = True

    ufp.api.get_camera = AsyncMock(side_effect=[doorbell, new_doorbell])
    ufp.api.create_camera_rtsps_streams = AsyncMock(return_value=None)
    issue_id = f"rtsp_disabled_{doorbell.id}"

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == issue_id:
            issue = i
    assert issue is not None

    # Unload the integration to ensure the fix flow still works
    # if the integration is no longer set up
    await hass.config_entries.async_unload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"

    ufp.api.create_camera_rtsps_streams.assert_called_with(doorbell.id, "high")


async def test_rtsp_no_fix_if_third_party(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test no RTSP disabled warning if camera is third-party."""

    for channel in doorbell.channels:
        channel.is_rtsp_enabled = False
    for user in ufp.api.bootstrap.users.values():
        user.all_permissions = []

    ufp.api.get_camera = AsyncMock(return_value=doorbell)
    doorbell.is_third_party_camera = True

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert not msg["result"]["issues"]


async def test_rtsp_no_fix_if_globally_disabled(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test no RTSP disabled warning if RTSP is globally disabled on integration."""

    for channel in doorbell.channels:
        channel.is_rtsp_enabled = False

    # Set RTSP globally disabled in config entry options
    hass.config_entries.async_update_entry(
        ufp.entry,
        options={**ufp.entry.options, CONF_DISABLE_RTSP: True},
    )

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)

    assert len(issue_registry.issues) == 0


async def test_public_stream_repair_cleared_on_private_path(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a stale public-stream repair is cleared when on the private path.

    Switching back from the public to the private stream path must drop the
    now-meaningless ``public_stream_disabled`` repair (it is non-persistent and
    would otherwise linger until the next restart).
    """
    issue_id = f"public_stream_disabled_{doorbell.id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="public_stream_disabled",
        translation_placeholders={"camera": doorbell.display_name},
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)
    await async_process_repairs_platforms(hass)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
