"""Test the Bosch Smart Home Camera number platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_shc_camera.const import (
    CLOUD_API,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TEST_BEARER_TOKEN, TEST_REFRESH_TOKEN, setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

# Fake camera IDs — arbitrary, not tied to any real Bosch device.
CAM_360 = "11111111-1111-1111-1111-111111111111"
CAM_EYES = "22222222-2222-2222-2222-222222222222"
CAM_OUTDOOR2 = "33333333-3333-3333-3333-333333333333"
CAM_INDOOR2 = "44444444-4444-4444-4444-444444444444"

VIDEO_INPUTS: list[dict[str, Any]] = [
    {
        "id": CAM_360,
        "title": "Wohnzimmer",
        "hardwareVersion": "CAMERA_360",
        "firmwareVersion": "7.91.56",
        "featureSupport": {"panLimit": 120, "light": False},
    },
    {
        "id": CAM_EYES,
        "title": "Garten",
        "hardwareVersion": "CAMERA_EYES",
        "firmwareVersion": "7.91.56",
        "featureSupport": {"panLimit": 0, "light": True},
    },
    {
        "id": CAM_OUTDOOR2,
        "title": "Terrasse",
        "hardwareVersion": "HOME_Eyes_Outdoor",
        "firmwareVersion": "9.40.104",
        "featureSupport": {"panLimit": 0, "light": True},
    },
    {
        "id": CAM_INDOOR2,
        "title": "Flur",
        "hardwareVersion": "HOME_Eyes_Indoor",
        "firmwareVersion": "9.40.104",
        "featureSupport": {"panLimit": 0, "light": False},
    },
]


def _mock_bootstrap_endpoints(aioclient_mock: AiohttpClientMocker) -> None:
    """Register the mocks every coordinator first-tick unconditionally needs.

    Same pattern as `test_init.py`'s `_mock_bootstrap_endpoints` — the
    first coordinator tick unconditionally calls `GET /v11/video_inputs`,
    `GET /v11/feature_flags` and `GET /protocol_support`.
    """
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs", json=VIDEO_INPUTS)
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})


async def _entity_id(hass: HomeAssistant, unique_id: str) -> str:
    """Resolve a number entity_id from its unique_id via the entity registry."""
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(NUMBER_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None, f"no entity registered for unique_id={unique_id}"
    return entity_id


def _patch_shc_session(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Patch `shc.py`'s own directly-imported cloud-session getter.

    `shc.py` does `from .cloud_ssl import async_get_bosch_cloud_session` at
    module level — a direct name binding into `shc`'s own namespace at
    import time. `conftest.py`'s autouse `aioclient_mock` fixture only
    patches the `cloud_ssl`/`__init__`/`config_flow` module-attribute
    lookups (per its own docstring) — it does NOT cover this fourth
    call site, so any test exercising a `shc.py` cloud setter (pan, light
    components, privacy mode, camera light, notifications) needs this
    extra patch or the write attempts a real network connection.
    """
    session = aioclient_mock.create_session(hass.loop)
    return session, patch(
        "homeassistant.components.bosch_shc_camera.shc.async_get_bosch_cloud_session",
        AsyncMock(return_value=session),
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Bulk entity-creation coverage across Gen1 360/Eyes + Gen2 Outdoor/Indoor cameras.

    Covers every number entity class number.py can create: pan (360 only),
    speaker/mic level, audio volume, front light intensity, lens elevation,
    intrusion sensitivity/distance, white balance, top/bottom LED
    brightness, motion light sensitivity, darkness threshold (Gen2
    non-indoor), power-LED brightness + 3 alarm delays (Gen2 Indoor).

    A dedicated config entry (not the shared `config_entry` fixture) is
    used with `enable_binary_sensors` forced off + `ALL_PLATFORMS` patched
    to just NUMBER — `snapshot_platform` requires exactly one entity
    platform to have been set up for the entry.
    """
    _mock_bootstrap_endpoints(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bosch Smart Home Camera",
        unique_id=DOMAIN,
        version=3,
        data={
            "bearer_token": TEST_BEARER_TOKEN,
            "refresh_token": TEST_REFRESH_TOKEN,
        },
        options={**DEFAULT_OPTIONS, "enable_binary_sensors": False},
    )

    with patch(
        "homeassistant.components.bosch_shc_camera.ALL_PLATFORMS",
        [Platform.NUMBER],
    ):
        await setup_integration(hass, entry)
        await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_pan_number_set_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Setting the pan number PUTs the absolute position and updates the cache.

    Also exercises both ends of the -120..+120 range (matches the camera's
    `featureSupport.panLimit` fixture value), pinning native_min_value/
    native_max_value to the actual API-reported limit.

    `async_cloud_set_pan` (shc.py) updates `pan_cache` and calls
    `coordinator.async_update_listeners()` itself on success, so
    `hass.states` reflects the write without any extra nudging from the
    test.
    """
    _mock_bootstrap_endpoints(aioclient_mock)
    # A single 204-no-body mock, reused for all 3 writes below:
    # `AiohttpClientMocker.match_request` always returns the FIRST
    # registered mock matching method+URL (it is not a per-call queue),
    # so registering 3 mocks with distinct JSON bodies for the same
    # method+URL would always match the first one regardless of what was
    # actually sent. A 204 leaves `result.body` as `None`, so
    # `async_cloud_set_pan` (shc.py) falls back to the *requested*
    # position instead of echoing a fixed response body.
    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_360}/pan",
        status=204,
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    entity_id = await _entity_id(hass, f"bosch_shc_pan_{CAM_360.lower()}")

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.attributes["min"]) == -120
    assert float(state.attributes["max"]) == 120

    # `BoschPanNumber.available` requires a cached pan position — a
    # brand-new entity starts "unavailable" (no first poll yet), and
    # HA's `number.set_value` service silently no-ops on an unavailable
    # target instead of raising. Seed a position + refresh listeners so
    # the entity is available before exercising the write path, matching
    # a camera that has already reported its position once.
    coordinator.pan_cache[CAM_360] = 0
    coordinator.async_update_listeners()
    assert hass.states.get(entity_id).state == "0.0"

    session, session_patch = _patch_shc_session(hass, aioclient_mock)
    try:
        with session_patch:
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 45},
                blocking=True,
            )
            assert coordinator.pan_cache[CAM_360] == 45
            put_calls = [
                c
                for c in aioclient_mock.mock_calls
                if c[0].lower() == "put" and str(c[1]).endswith(f"/{CAM_360}/pan")
            ]
            assert put_calls[-1][2] == {"absolutePosition": 45}
            assert hass.states.get(entity_id).state == "45.0"

            # Boundary: minimum.
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: -120},
                blocking=True,
            )
            assert coordinator.pan_cache[CAM_360] == -120
            put_calls = [
                c
                for c in aioclient_mock.mock_calls
                if c[0].lower() == "put" and str(c[1]).endswith(f"/{CAM_360}/pan")
            ]
            assert put_calls[-1][2] == {"absolutePosition": -120}

            # Boundary: maximum.
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 120},
                blocking=True,
            )
            assert coordinator.pan_cache[CAM_360] == 120
            put_calls = [
                c
                for c in aioclient_mock.mock_calls
                if c[0].lower() == "put" and str(c[1]).endswith(f"/{CAM_360}/pan")
            ]
            assert put_calls[-1][2] == {"absolutePosition": 120}
    finally:
        await session.close()


async def test_front_light_intensity_scale_conversion(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Setting front light intensity converts HA's 0-100% into Bosch's 0.0-1.0 float.

    Uses the Gen1 Eyes camera (`lighting_override` endpoint, single combined
    body). The endpoint rejects `frontLightIntensity` unless
    `frontLightOn` is already true (shc.py), so the coordinator's
    `shc_state_cache` must show the front light on before the write.

    `async_cloud_set_light_component` (shc.py) updates `shc_state_cache`
    and calls `coordinator.async_update_listeners()` itself on success, so
    `hass.states` reflects the new value without any extra nudging.
    """
    _mock_bootstrap_endpoints(aioclient_mock)
    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_EYES}/lighting_override",
        status=200,
        json={},
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.shc_state_cache[CAM_EYES] = {
        "front_light": True,
        "wallwasher": False,
        "front_light_intensity": 1.0,
    }
    coordinator.async_update_listeners()

    entity_id = await _entity_id(
        hass, f"bosch_shc_front_light_intensity_{CAM_EYES.lower()}"
    )
    assert hass.states.get(entity_id).state == "100.0"

    session, session_patch = _patch_shc_session(hass, aioclient_mock)
    try:
        with session_patch:
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 40},
                blocking=True,
            )
        put_calls = [
            c
            for c in aioclient_mock.mock_calls
            if c[0].lower() == "put"
            and str(c[1]).endswith(f"/{CAM_EYES}/lighting_override")
        ]
        assert put_calls[-1][2] == {
            "frontLightOn": True,
            "wallwasherOn": False,
            "frontLightIntensity": 0.4,
        }
        assert hass.states.get(entity_id).state == "40.0"
    finally:
        await session.close()


async def test_intrusion_sensitivity_set_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Setting intrusion sensitivity PUTs the full body with other fields preserved."""
    _mock_bootstrap_endpoints(aioclient_mock)
    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_OUTDOOR2}/intrusionDetectionConfig",
        status=200,
        json={},
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.intrusion_config_cache[CAM_OUTDOOR2] = {
        "sensitivity": 3,
        "distance": 5,
        "detectionMode": "PERSON",
        "enabled": True,
    }
    coordinator.async_update_listeners()

    entity_id = await _entity_id(
        hass, f"bosch_shc_camera_{CAM_OUTDOOR2}_intrusion_sensitivity"
    )
    assert hass.states.get(entity_id).state == "3.0"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 6},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == "6.0"
    put_calls = [
        c
        for c in aioclient_mock.mock_calls
        if c[0].lower() == "put"
        and str(c[1]).endswith(f"/{CAM_OUTDOOR2}/intrusionDetectionConfig")
    ]
    assert put_calls[-1][2] == {
        "sensitivity": 6,
        "distance": 5,
        "detectionMode": "PERSON",
        "enabled": True,
    }


async def test_intrusion_distance_boundary_values(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Intrusion distance native_min/max_value match the Bosch API's 1-8 m range.

    API rejects `distance > 8` with HTTP 400 (verified live FW 9.40.102) —
    pins both the entity's advertised range and the write-time clamp.
    """
    _mock_bootstrap_endpoints(aioclient_mock)
    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_OUTDOOR2}/intrusionDetectionConfig",
        status=200,
        json={},
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.intrusion_config_cache[CAM_OUTDOOR2] = {
        "sensitivity": 3,
        "distance": 5,
        "detectionMode": "PERSON",
        "enabled": True,
    }
    coordinator.async_update_listeners()

    entity_id = await _entity_id(
        hass, f"bosch_shc_camera_{CAM_OUTDOOR2}_intrusion_distance"
    )
    state = hass.states.get(entity_id)
    assert float(state.attributes["min"]) == 1
    assert float(state.attributes["max"]) == 8

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 1},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == "1.0"
    put_calls = [
        c
        for c in aioclient_mock.mock_calls
        if c[0].lower() == "put"
        and str(c[1]).endswith(f"/{CAM_OUTDOOR2}/intrusionDetectionConfig")
    ]
    assert put_calls[-1][2]["distance"] == 1

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 8},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == "8.0"
    put_calls = [
        c
        for c in aioclient_mock.mock_calls
        if c[0].lower() == "put"
        and str(c[1]).endswith(f"/{CAM_OUTDOOR2}/intrusionDetectionConfig")
    ]
    assert put_calls[-1][2]["distance"] == 8
