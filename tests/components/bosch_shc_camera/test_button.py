"""Test the Bosch Smart Home Camera button platform."""

import pytest

from homeassistant.components.bosch_shc_camera.const import CLOUD_API, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CAM_ID = "aabbccdd-1122-3344-5566-778899001122"


def _mock_video_inputs(aioclient_mock: AiohttpClientMocker) -> None:
    """Register the camera list plus the always-needed bootstrap endpoints."""
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


async def test_refresh_snapshot_button_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Pressing the refresh-snapshot button triggers a coordinator refresh in the background."""
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)

    # The background refresh needs a second bootstrap round mocked, since
    # `async_request_refresh()` re-runs the same first-tick endpoint set.
    aioclient_mock.clear_requests()
    _mock_video_inputs(aioclient_mock)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.bosch_terrasse_refresh_snapshot"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert any(
        call[0].lower() == "get" and str(call[1]).endswith("/v11/video_inputs")
        for call in aioclient_mock.mock_calls
    )


async def test_soft_reset_button_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Pressing the (registry-enabled) soft-reset button PUTs the soft_reset endpoint."""
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)

    entity_registry = er.async_get(hass)
    entity_id = "button.bosch_terrasse_restart_camera"
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is not None
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/soft_reset",
        status=200,
        json={},
    )

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    put_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "put" and str(call[1]).endswith("/soft_reset")
    ]
    assert len(put_calls) == 1


async def test_soft_reset_button_press_failure_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A rejected soft-reset PUT surfaces as a HomeAssistantError, not silently swallowed."""
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)

    entity_registry = er.async_get(hass)
    entity_id = "button.bosch_terrasse_restart_camera"
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/soft_reset",
        status=404,
        json={"error": "sh:entity.notfound"},
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )


async def test_hard_reset_button_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Pressing the (registry-enabled) hard-reset button PUTs the hard_reset endpoint."""
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)

    entity_registry = er.async_get(hass)
    entity_id = "button.bosch_terrasse_factory_reset_camera"
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is not None
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/hard_reset",
        status=200,
        json={},
    )

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    put_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "put" and str(call[1]).endswith("/hard_reset")
    ]
    assert len(put_calls) == 1


async def test_snapshot_button_disabled_by_option(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`enable_snapshot_button=False` skips creating the refresh-snapshot button entity."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={**config_entry.options, "enable_snapshot_button": False},
    )
    _mock_video_inputs(aioclient_mock)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("button.bosch_terrasse_refresh_snapshot") is None
    # The reset buttons are unaffected by this option and still register
    # (disabled-by-default, but present in the entity registry).
    entity_registry = er.async_get(hass)
    assert (
        entity_registry.async_get_entity_id(
            "button", DOMAIN, f"bosch_shc_soft_reset_{CAM_ID}"
        )
        is not None
    )
