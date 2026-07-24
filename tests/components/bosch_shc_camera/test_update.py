"""Test the Bosch Smart Home Camera firmware update entity.

Coverage split with test_repairs.py: the Repairs-issue creation/fix-flow
(`firmware_update_available`) is tested there. This file focuses on the
`update.*` entity's own state/attributes and its Install action.
"""

import pytest

from homeassistant.components.bosch_shc_camera.const import CLOUD_API
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CAM_ID = "aabbccdd-1122-3344-5566-778899001122"
ENTITY_ID = "update.bosch_terrasse_firmware"


def _mock_video_inputs(aioclient_mock: AiohttpClientMocker) -> None:
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


async def test_update_entity_up_to_date(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """When the firmware slow-tier reports upToDate, installed==latest and off state."""
    _mock_video_inputs(aioclient_mock)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={"upToDate": True, "current": "9.40.104", "update": "9.40.104"},
    )
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["installed_version"] == "9.40.104"
    assert state.attributes["latest_version"] == "9.40.104"
    assert state.attributes["in_progress"] is False
    assert state.attributes["up_to_date"] is True


async def test_update_entity_pending_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A pending update reports the new version and up_to_date=False."""
    _mock_video_inputs(aioclient_mock)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={"upToDate": False, "current": "9.40.100", "update": "9.40.104"},
    )
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["installed_version"] == "9.40.100"
    assert state.attributes["latest_version"] == "9.40.104"
    assert state.attributes["up_to_date"] is False


async def test_update_entity_updating_in_progress(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """While Bosch reports `updating=true`, the entity's in_progress mirrors it."""
    _mock_video_inputs(aioclient_mock)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={
            "upToDate": False,
            "current": "9.40.100",
            "update": "9.40.104",
            "updating": True,
        },
    )
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["in_progress"] is True
    assert state.attributes["updating"] is True


async def test_update_entity_no_firmware_data_falls_back_to_base_fw(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Before the slow-tier ever populates firmware_cache, installed_version falls back to the base fw field."""
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["installed_version"] == "9.40.100"
    # latest_version falls back to installed_version when firmware_cache is empty.
    assert state.attributes["latest_version"] == "9.40.100"


async def test_update_install_service_calls_firmware_put(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`update.install` PUTs the firmware endpoint with the pending update's version."""
    _mock_video_inputs(aioclient_mock)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={"upToDate": False, "current": "9.40.100", "update": "9.40.104"},
    )
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={},
    )

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    put_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "put" and str(call[1]).endswith(f"/{CAM_ID}/firmware")
    ]
    assert len(put_calls) == 1
    assert put_calls[0][2] == {"id": "9.40.104"}
    assert coordinator.firmware_cache[CAM_ID]["updating"] is True


async def test_update_install_no_pending_update_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`async_install_firmware` refuses to PUT when no update is pending.

    Exercised directly against the coordinator method (not via the
    `update.install` service) — HA-core's own `UpdateEntity` service layer
    (`homeassistant/components/update/__init__.py`) already blocks
    `async_install` from ever being reached when the entity's own state
    is not "on" (no update available), raising ITS OWN untranslated
    `HomeAssistantError("No update available for ...")` first. That guard
    lives in core, not in this integration, and going through the service
    call would make this test fail the exception-translations quality-scale
    check for an error message this integration never raises. Calling the
    coordinator method directly isolates the behavior actually owned here.
    """
    _mock_video_inputs(aioclient_mock)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/firmware",
        json={"upToDate": True, "current": "9.40.104"},
    )
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    with pytest.raises(HomeAssistantError):
        await coordinator.async_install_firmware(CAM_ID)

    assert not any(
        call[0].lower() == "put" and str(call[1]).endswith(f"/{CAM_ID}/firmware")
        for call in aioclient_mock.mock_calls
    )
