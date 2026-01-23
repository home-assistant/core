"""Test repairs for unifiprotect."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from uiprotect.data import Camera, CloudAccount, Version

from homeassistant.components.unifiprotect.const import CONF_DISABLE_RTSP, DOMAIN
from homeassistant.components.unifiprotect.repairs import async_create_fix_flow
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import create_mock_rtsps_streams
from .utils import MockUFPFixture, init_entry

from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


def _setup_camera_with_active_streams(
    camera: Camera, include_create: bool = True
) -> Camera:
    """Create a camera copy with active RTSPS streams mocked.

    Args:
        camera: The source camera to copy
        include_create: If True, also mock create_rtsps_streams (for writable users)
    """
    new_camera = deepcopy(camera)
    new_camera.channels[0].is_rtsp_enabled = True
    mock_streams = create_mock_rtsps_streams(["high", "medium", "low"])
    object.__setattr__(
        new_camera, "get_rtsps_streams", AsyncMock(return_value=mock_streams)
    )
    if include_create:
        object.__setattr__(
            new_camera, "create_rtsps_streams", AsyncMock(return_value=mock_streams)
        )
    return new_camera


def _disable_all_rtsp_channels(camera: Camera) -> None:
    """Disable RTSP on all channels of a camera."""
    for channel in camera.channels:
        channel.is_rtsp_enabled = False


def _make_users_read_only(ufp: MockUFPFixture) -> None:
    """Remove all permissions from users to simulate read-only access."""
    for user in ufp.api.bootstrap.users.values():
        user.all_permissions = []


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


@pytest.fixture
def rtsps_disabled() -> bool:
    """Disable RTSPS streams for this test."""
    return True


async def test_rtsp_read_only_ignore(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    rtsps_disabled: bool,
) -> None:
    """Test RTSP disabled warning if camera is read-only and it is ignored."""
    _disable_all_rtsp_channels(doorbell)
    _make_users_read_only(ufp)

    ufp.api.get_camera = AsyncMock(return_value=doorbell)

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
    rtsps_disabled: bool,
) -> None:
    """Test RTSP disabled warning if camera is read-only and it is fixed.

    Scenario: User has read-only permissions but someone else activated streams.
    The repair flow should detect this and complete successfully.
    """
    _disable_all_rtsp_channels(doorbell)
    _make_users_read_only(ufp)

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    # After init, simulate that someone else activated the streams
    new_doorbell = _setup_camera_with_active_streams(doorbell, include_create=False)
    new_doorbell.channels[1].is_rtsp_enabled = True
    ufp.api.get_camera = AsyncMock(return_value=new_doorbell)
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
    rtsps_disabled: bool,
) -> None:
    """Test RTSP disabled warning if camera is writable and streams are activated."""
    _disable_all_rtsp_channels(doorbell)

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    new_doorbell = _setup_camera_with_active_streams(doorbell)
    ufp.api.get_camera = AsyncMock(return_value=new_doorbell)
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


async def test_rtsp_writable_fix_when_not_setup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    rtsps_disabled: bool,
) -> None:
    """Test RTSP disabled warning if the integration is no longer set up."""
    _disable_all_rtsp_channels(doorbell)

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    new_doorbell = _setup_camera_with_active_streams(doorbell)
    ufp.api.get_camera = AsyncMock(return_value=new_doorbell)
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


async def test_rtsp_no_fix_if_third_party(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_ws_client: WebSocketGenerator,
    rtsps_disabled: bool,
) -> None:
    """Test no RTSP disabled warning if camera is third-party."""
    _disable_all_rtsp_channels(doorbell)
    _make_users_read_only(ufp)

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
    rtsps_disabled: bool,
) -> None:
    """Test no RTSP disabled warning if RTSP is globally disabled on integration."""
    _disable_all_rtsp_channels(doorbell)

    # Set RTSP globally disabled in config entry options
    hass.config_entries.async_update_entry(
        ufp.entry,
        options={**ufp.entry.options, CONF_DISABLE_RTSP: True},
    )

    await init_entry(hass, ufp, [doorbell])
    await async_process_repairs_platforms(hass)

    assert len(issue_registry.issues) == 0


async def test_unknown_issue_returns_confirm_flow(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that unknown issue_id returns ConfirmRepairFlow."""
    await init_entry(hass, ufp, [])

    # Test with None data
    flow = await async_create_fix_flow(hass, "unknown_issue", None)
    assert flow.__class__.__name__ == "ConfirmRepairFlow"

    # Test with invalid entry_id
    flow = await async_create_fix_flow(
        hass, "unknown_issue", {"entry_id": "nonexistent"}
    )
    assert flow.__class__.__name__ == "ConfirmRepairFlow"

    # Test with valid entry but unknown issue_id
    flow = await async_create_fix_flow(
        hass, "unknown_issue", {"entry_id": ufp.entry.entry_id}
    )
    assert flow.__class__.__name__ == "ConfirmRepairFlow"
