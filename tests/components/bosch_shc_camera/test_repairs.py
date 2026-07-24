"""Test the Bosch Smart Home Camera firmware-update Repairs flow."""

from homeassistant.components.bosch_shc_camera.const import CLOUD_API, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CAM_ID = "aabbccdd-1122-3344-5566-778899001122"
ISSUE_ID = f"firmware_update_available_{CAM_ID}"


def _mock_video_inputs(aioclient_mock: AiohttpClientMocker) -> None:
    """Register the camera list — Gen1 hardware keeps the slow-tier endpoint set small."""
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs",
        json=[
            {
                "id": CAM_ID,
                "title": "Terrasse",
                "hardwareVersion": "CAMERA_EYES",
                "firmwareVersion": "9.40.100",
                "privacyMode": "OFF",
                "featureSupport": {},
            }
        ],
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/ping", text='"ONLINE"')


async def test_firmware_update_issue_created_and_fixed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A pending firmware update raises a fixable Repairs issue; the fix flow installs it.

    `firmware_cache` is only populated by the slow-tier pass, which the
    fast first tick deliberately skips (`tick_bootstrap.py` — first-tick
    fast path). A second `async_refresh()` (still the coordinator's public
    API, not an internal poke) runs the slow tier for real against the
    mocked `/firmware` endpoint, exactly reproducing how this issue is
    raised in production.
    """
    assert await async_setup_component(hass, "repairs", {})
    _mock_video_inputs(aioclient_mock)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={"upToDate": False, "current": "9.40.100", "update": "9.40.104"},
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_key == "firmware_update_available"
    assert issue.translation_placeholders == {
        "camera": "Terrasse",
        "current": "9.40.100",
        "latest": "9.40.104",
    }

    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={},
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {
        "camera": "Terrasse",
        "current": "9.40.100",
        "latest": "9.40.104",
    }

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == "create_entry"
    assert coordinator.firmware_cache[CAM_ID]["updating"] is True

    put_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "put" and str(call[1]).endswith(f"/{CAM_ID}/firmware")
    ]
    assert len(put_calls) == 1
    assert put_calls[0][2] == {"id": "9.40.104"}


async def test_firmware_up_to_date_clears_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Once a camera reports upToDate again, the issue is deleted."""
    assert await async_setup_component(hass, "repairs", {})
    _mock_video_inputs(aioclient_mock)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={"upToDate": True, "current": "9.40.104", "update": "9.40.104"},
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
