"""Test repairs for the unifiprotect public-API stream path."""

from unittest.mock import AsyncMock

import pytest
from uiprotect.api import RTSPSStreams
from uiprotect.data import Camera
from uiprotect.exceptions import NotAuthorized

from homeassistant.components.unifiprotect.const import (
    CONF_DISABLE_RTSP,
    CONF_USE_PUBLIC_API_STREAMS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .utils import MockUFPFixture, init_entry

from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator

_ACTIVE_STREAMS = RTSPSStreams(high="rtsps://example.test:7441/abc?enableSrtp")
_NO_STREAMS = RTSPSStreams()


@pytest.fixture(name="ufp_options")
def _public_stream_options() -> dict[str, bool]:
    """Use the public-API stream path."""
    return {CONF_USE_PUBLIC_API_STREAMS: True}


@pytest.fixture(autouse=True)
def _primed_public_bootstrap(ufp: MockUFPFixture) -> None:
    """The public stream path reads streams from a primed public bootstrap."""
    ufp.api.has_public_bootstrap = True


async def _raise_and_assert_repair(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> tuple[ClientSessionGenerator, str]:
    """Set up a streamless camera, assert its repair exists, return (client, issue_id)."""
    for channel in camera.channels:
        channel.is_rtsp_enabled = False

    await init_entry(hass, ufp, [camera])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issue_id = f"public_stream_disabled_{camera.id}"
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert any(i["issue_id"] == issue_id for i in msg["result"]["issues"])
    return client, issue_id


async def test_public_stream_repair_fix(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A camera without an active stream raises a repair that creates one."""
    client, issue_id = await _raise_and_assert_repair(
        hass, ufp, camera, hass_client, hass_ws_client
    )

    # Model the device: no stream until one is created.
    state = {"created": False}

    async def get_streams(camera_id: str, *args, **kwargs) -> RTSPSStreams:
        return _ACTIVE_STREAMS if state["created"] else _NO_STREAMS

    async def create_streams(
        camera_id: str, qualities, *args, **kwargs
    ) -> RTSPSStreams:
        state["created"] = True
        return _ACTIVE_STREAMS

    ufp.api.get_camera_rtsps_streams = AsyncMock(side_effect=get_streams)
    ufp.api.create_camera_rtsps_streams = AsyncMock(side_effect=create_streams)

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, data["flow_id"])
    assert data["type"] == "create_entry"

    ufp.api.create_camera_rtsps_streams.assert_called_with(camera.id, "high")


@pytest.mark.parametrize(
    "create_side_effect",
    [
        pytest.param(None, id="unresolved"),
        pytest.param(NotAuthorized("missing write permission"), id="no_permission"),
    ],
)
async def test_public_stream_repair_confirm_fallback(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    create_side_effect: Exception | None,
) -> None:
    """When a stream cannot be created, the flow falls back to a confirm step.

    Covers both an unresolved create (still no active stream) and a permission
    error while creating; both route start -> confirm -> create_entry.
    """
    client, issue_id = await _raise_and_assert_repair(
        hass, ufp, camera, hass_client, hass_ws_client
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


async def test_public_stream_no_repair_if_active(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera_all: Camera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """No repair when the default high stream is active."""
    await init_entry(hass, ufp, [camera_all])

    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"public_stream_disabled_{camera_all.id}"
        )
        is None
    )


@pytest.mark.parametrize(
    ("third_party", "extra_options"),
    [
        pytest.param(True, {}, id="third_party"),
        pytest.param(False, {CONF_DISABLE_RTSP: True}, id="globally_disabled"),
    ],
)
async def test_public_stream_no_repair_when_suppressed(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    issue_registry: ir.IssueRegistry,
    third_party: bool,
    extra_options: dict[str, bool],
) -> None:
    """No repair for third-party cameras or when RTSP is globally disabled."""
    for channel in camera.channels:
        channel.is_rtsp_enabled = False
    camera.is_third_party_camera = third_party
    hass.config_entries.async_update_entry(
        ufp.entry, options={**ufp.entry.options, **extra_options}
    )

    await init_entry(hass, ufp, [camera])

    assert (
        issue_registry.async_get_issue(DOMAIN, f"public_stream_disabled_{camera.id}")
        is None
    )
