"""Test repairs for unifiprotect."""

from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient
import pytest
from uiprotect.api import RTSPSStreams
from uiprotect.data import Camera, CloudAccount, Version
from uiprotect.exceptions import NotAuthorized

from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.components.unifiprotect.const import CONF_DISABLE_RTSP, DOMAIN
from homeassistant.components.unifiprotect.repairs import async_create_fix_flow
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .utils import MockUFPFixture, init_entry

from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator, WebSocketGenerator

_ACTIVE_STREAMS = RTSPSStreams(high="rtsps://example.test:7441/abc?enableSrtp")
_NO_STREAMS = RTSPSStreams()


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
    assert await async_setup_component(hass, "repairs", {})
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


async def _raise_and_assert_repair(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> tuple[TestClient, str]:
    """Set up a streamless camera, assert its repair exists, return (client, issue_id)."""
    for channel in doorbell.channels:
        channel.is_rtsp_enabled = False

    await init_entry(hass, ufp, [doorbell])
    assert await async_setup_component(hass, "repairs", {})
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issue_id = f"rtsp_disabled_{doorbell.id}"
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert any(i["issue_id"] == issue_id for i in msg["result"]["issues"])
    return client, issue_id


async def test_rtsp_repair_fix(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A camera without an active stream raises a repair that creates one."""
    client, issue_id = await _raise_and_assert_repair(
        hass, ufp, doorbell, hass_client, hass_ws_client
    )

    # Model the device: no stream until one is created (via the public API).
    state = {"created": False}

    async def get_streams(
        camera_id: str, *args: object, **kwargs: object
    ) -> RTSPSStreams:
        return _ACTIVE_STREAMS if state["created"] else _NO_STREAMS

    async def create_streams(
        camera_id: str, qualities: str, *args: object, **kwargs: object
    ) -> RTSPSStreams:
        state["created"] = True
        return _ACTIVE_STREAMS

    ufp.api.get_camera_rtsps_streams = AsyncMock(side_effect=get_streams)
    ufp.api.create_camera_rtsps_streams = AsyncMock(side_effect=create_streams)

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, data["flow_id"])
    assert data["type"] == "create_entry"

    ufp.api.create_camera_rtsps_streams.assert_called_with(doorbell.id, "high")


@pytest.mark.parametrize(
    "create_side_effect",
    [
        pytest.param(None, id="unresolved"),
        pytest.param(NotAuthorized("missing write permission"), id="no_permission"),
    ],
)
async def test_rtsp_repair_confirm_fallback(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    create_side_effect: Exception | None,
) -> None:
    """When a stream cannot be created, the flow falls back to a confirm step.

    Covers both an unresolved create (still no active stream) and a permission
    error while creating; both route start -> confirm -> create_entry.
    """
    client, issue_id = await _raise_and_assert_repair(
        hass, ufp, doorbell, hass_client, hass_ws_client
    )

    ufp.api.get_camera_rtsps_streams = AsyncMock(return_value=_NO_STREAMS)
    ufp.api.create_camera_rtsps_streams = AsyncMock(
        return_value=_NO_STREAMS, side_effect=create_side_effect
    )

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, data["flow_id"])
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, data["flow_id"])
    assert data["type"] == "create_entry"


async def test_create_fix_flow_unknown_issue(hass: HomeAssistant) -> None:
    """An issue without matching data falls back to a confirm-only flow."""
    flow = await async_create_fix_flow(hass, "some_other_issue", None)
    assert isinstance(flow, ConfirmRepairFlow)


async def test_rtsp_repair_when_not_setup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The repair works while the entry is unloaded (fresh API client)."""
    client, issue_id = await _raise_and_assert_repair(
        hass, ufp, doorbell, hass_client, hass_ws_client
    )

    await hass.config_entries.async_unload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    state = {"created": False}

    async def get_streams(
        camera_id: str, *args: object, **kwargs: object
    ) -> RTSPSStreams:
        return _ACTIVE_STREAMS if state["created"] else _NO_STREAMS

    async def create_streams(
        camera_id: str, qualities: str, *args: object, **kwargs: object
    ) -> RTSPSStreams:
        state["created"] = True
        return _ACTIVE_STREAMS

    ufp.api.get_camera_rtsps_streams = AsyncMock(side_effect=get_streams)
    ufp.api.create_camera_rtsps_streams = AsyncMock(side_effect=create_streams)

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, data["flow_id"])
    assert data["type"] == "create_entry"


async def test_rtsp_no_repair_if_active(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """No repair when the default high stream is active."""
    await init_entry(hass, ufp, [doorbell])

    assert (
        issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{doorbell.id}") is None
    )


@pytest.mark.parametrize(
    ("third_party", "extra_options"),
    [
        pytest.param(True, {}, id="third_party"),
        pytest.param(False, {CONF_DISABLE_RTSP: True}, id="globally_disabled"),
    ],
)
async def test_rtsp_no_repair_when_suppressed(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    issue_registry: ir.IssueRegistry,
    third_party: bool,
    extra_options: dict[str, bool],
) -> None:
    """No repair for third-party cameras or when RTSP is globally disabled."""
    for channel in doorbell.channels:
        channel.is_rtsp_enabled = False
    doorbell.is_third_party_camera = third_party
    hass.config_entries.async_update_entry(
        ufp.entry, options={**ufp.entry.options, **extra_options}
    )

    await init_entry(hass, ufp, [doorbell])

    assert (
        issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{doorbell.id}") is None
    )
