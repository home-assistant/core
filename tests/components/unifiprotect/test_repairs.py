"""Test repairs for unifiprotect."""

from __future__ import annotations

from copy import copy, deepcopy
from unittest.mock import AsyncMock, Mock

from uiprotect.data import Camera, CloudAccount, ModelType, Version

from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture, init_entry

from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_ea_warning_ignore(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test EA warning is created if using prerelease version of Protect."""

    ufp.api.bootstrap.nvr.release_channel = "beta"
    ufp.api.bootstrap.nvr.version = Version("1.21.0-beta.2")
    version = ufp.api.bootstrap.nvr.version
    assert version.is_prerelease
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
        if i["issue_id"] == "ea_channel_warning":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "ea_channel_warning")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "learn_more": "https://www.home-assistant.io/integrations/unifiprotect#software-support",
        "version": str(version),
    }
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, flow_id)

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "learn_more": "https://www.home-assistant.io/integrations/unifiprotect#software-support",
        "version": str(version),
    }
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"


async def test_ea_warning_fix(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test EA warning is created if using prerelease version of Protect."""

    ufp.api.bootstrap.nvr.release_channel = "beta"
    ufp.api.bootstrap.nvr.version = Version("1.21.0-beta.2")
    version = ufp.api.bootstrap.nvr.version
    assert version.is_prerelease
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
        if i["issue_id"] == "ea_channel_warning":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "ea_channel_warning")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "learn_more": "https://www.home-assistant.io/integrations/unifiprotect#software-support",
        "version": str(version),
    }
    assert data["step_id"] == "start"

    new_nvr = copy(ufp.api.bootstrap.nvr)
    new_nvr.release_channel = "release"
    new_nvr.version = Version("2.2.6")
    mock_msg = Mock()
    mock_msg.changed_data = {"version": "2.2.6", "releaseChannel": "release"}
    mock_msg.new_obj = new_nvr

    ufp.api.bootstrap.nvr = new_nvr
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"


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
    ufp.api.update_device = AsyncMock()
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

    channels = doorbell.unifi_dict()["channels"]
    channels[0]["isRtspEnabled"] = True
    ufp.api.update_device.assert_called_with(
        ModelType.CAMERA, doorbell.id, {"channels": channels}
    )


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
    ufp.api.update_device = AsyncMock()
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

    channels = doorbell.unifi_dict()["channels"]
    channels[0]["isRtspEnabled"] = True
    ufp.api.update_device.assert_called_with(
        ModelType.CAMERA, doorbell.id, {"channels": channels}
    )


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
