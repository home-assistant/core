"""Test the Bosch Smart Home Camera light platform (Gen2 top/bottom LED + front light)."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.bosch_shc_camera.const import CLOUD_API
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CAM_ID = "aabbccdd-1122-3344-5566-778899001122"


@pytest.fixture(autouse=True)
def _patch_light_module_session(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> Generator[None]:
    """Work around a conftest.py test-infra gap for light.py's write paths.

    `light.py` does `from .cloud_ssl import async_get_bosch_cloud_session` — a
    by-value import that binds the name once, the first time
    `homeassistant.components.bosch_shc_camera.light` is imported in this
    pytest *process* (module caching via `sys.modules`). conftest.py's
    `aioclient_mock` fixture only patches `cloud_ssl.async_get_bosch_cloud_session`
    plus the separately-reimported `__init__.py`/`config_flow.py` names — it
    does NOT patch `light.async_get_bosch_cloud_session`. Verified live
    (added temporary tracing, since removed): once any earlier test in the
    session has imported `light.py`, every LATER test's light-entity writes
    (`_put_lighting_switch`/`_put_switch_endpoint`) silently run against that
    FIRST test's already-closed session/mocker instead of the current test's
    — the write can still "succeed" (same CAM_ID, same URLs registered
    against the stale mocker) while the current test's own `aioclient_mock`
    fixture never sees the PUT at all. The same gap exists for
    switch.py/camera.py/fcm.py/rcp.py/shc.py (all import directly from
    `.cloud_ssl` too) — flagged, not fixed here since this file is scoped to
    light.py only and conftest.py is shared with sibling platform test files.
    """
    session = aioclient_mock.create_session(hass.loop)
    with patch(
        "homeassistant.components.bosch_shc_camera.light.async_get_bosch_cloud_session",
        new=AsyncMock(return_value=session),
    ):
        yield


TOP_LED_UNIQUE_ID = f"bosch_shc_camera_{CAM_ID}_top_led_light"
BOTTOM_LED_UNIQUE_ID = f"bosch_shc_camera_{CAM_ID}_bottom_led_light"
FRONT_LIGHT_UNIQUE_ID = f"bosch_shc_camera_{CAM_ID}_front_light_entity"


def _mock_video_inputs(
    aioclient_mock: AiohttpClientMocker,
    *,
    has_light: bool = True,
) -> None:
    """Register a Gen2 camera with (or without) controllable lights."""
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs",
        json=[
            {
                "id": CAM_ID,
                "title": "Terrasse",
                "hardwareVersion": "HOME_Eyes_Outdoor",
                "firmwareVersion": "9.40.104",
                "privacyMode": "OFF",
                "macAddress": "aa:bb:cc:dd:ee:ff",
                "featureSupport": {"light": has_light},
            }
        ],
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/ping", text='"ONLINE"')
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting/switch",
        json={
            "frontLightSettings": {
                "brightness": 0,
                "color": None,
                "whiteBalance": -1.0,
            },
            "topLedLightSettings": {
                "brightness": 0,
                "color": None,
                "whiteBalance": -1.0,
            },
            "bottomLedLightSettings": {
                "brightness": 0,
                "color": None,
                "whiteBalance": -1.0,
            },
        },
    )


def _mock_lighting_switch_put(aioclient_mock: AiohttpClientMocker) -> None:
    """Register the write endpoints every light turn_on/turn_off exercises."""
    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting/switch",
        status=204,
    )
    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting/switch/topdown",
        status=204,
    )
    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting/switch/front",
        status=204,
    )


def _last_put_body(
    aioclient_mock: AiohttpClientMocker, url_suffix: str
) -> dict[str, Any]:
    """Return the JSON body of the most recent PUT matching url_suffix."""
    matches = [
        data
        for method, url, data, _headers in aioclient_mock.mock_calls
        if method.lower() == "put" and str(url).endswith(url_suffix)
    ]
    assert matches, f"no PUT recorded for {url_suffix}"
    return matches[-1]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A Gen2 camera with light support creates exactly the 3 light entities, each with the expected name/state.

    `snapshot_platform` isn't used here: `async_setup_entry` forwards ALL
    enabled platforms in one `async_forward_entry_setups` call (not just
    "light"), so `snapshot_platform`'s own "limit to 1 platform" assertion
    would fail regardless of what this test does — asserted explicitly
    instead.
    """
    _mock_video_inputs(aioclient_mock)

    await setup_integration(hass, config_entry)

    for unique_id, name, expected_state in (
        (TOP_LED_UNIQUE_ID, "Bosch Terrasse Top LED", STATE_OFF),
        (BOTTOM_LED_UNIQUE_ID, "Bosch Terrasse Bottom LED", STATE_OFF),
        (FRONT_LIGHT_UNIQUE_ID, "Bosch Terrasse Front light", STATE_OFF),
    ):
        entity_id = entity_registry.async_get_entity_id(
            LIGHT_DOMAIN, "bosch_shc_camera", unique_id
        )
        assert entity_id is not None, f"no entity registered for {unique_id}"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state
        assert state.attributes["friendly_name"] == name


async def test_no_light_entities_without_feature_support(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A Gen2 camera reporting featureSupport.light=False gets zero light entities."""
    _mock_video_inputs(aioclient_mock, has_light=False)

    await setup_integration(hass, config_entry)

    assert (
        entity_registry.async_get_entity_id(
            LIGHT_DOMAIN, "bosch_shc_camera", TOP_LED_UNIQUE_ID
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            LIGHT_DOMAIN, "bosch_shc_camera", BOTTOM_LED_UNIQUE_ID
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            LIGHT_DOMAIN, "bosch_shc_camera", FRONT_LIGHT_UNIQUE_ID
        )
        is None
    )


@pytest.mark.parametrize(
    ("unique_id", "led_key"),
    [
        (TOP_LED_UNIQUE_ID, "topLedLightSettings"),
        (BOTTOM_LED_UNIQUE_ID, "bottomLedLightSettings"),
        (FRONT_LIGHT_UNIQUE_ID, "frontLightSettings"),
    ],
    ids=["top_led", "bottom_led", "front_light"],
)
async def test_turn_on_default_brightness(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    unique_id: str,
    led_key: str,
) -> None:
    """turn_on with no explicit brightness restores the (default 100%) last brightness.

    The PUT body always contains all 3 light groups (`_get_current_state()`
    fixes the key order to front/top/bottom regardless of which light was
    toggled) — the test must look up its own `led_key`, not assume dict
    iteration order matches the entity under test.
    """
    _mock_video_inputs(aioclient_mock)
    _mock_lighting_switch_put(aioclient_mock)
    await setup_integration(hass, config_entry)

    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, "bosch_shc_camera", unique_id
    )
    assert entity_id is not None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    body = _last_put_body(aioclient_mock, "/lighting/switch")
    assert body[led_key]["brightness"] == 100


@pytest.mark.parametrize(
    ("unique_id", "led_key"),
    [
        (TOP_LED_UNIQUE_ID, "topLedLightSettings"),
        (BOTTOM_LED_UNIQUE_ID, "bottomLedLightSettings"),
    ],
    ids=["top_led", "bottom_led"],
)
async def test_rgb_turn_on_with_brightness_and_color(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    unique_id: str,
    led_key: str,
) -> None:
    """turn_on w/ explicit brightness+rgb_color converts HA's 0-255 scale to Bosch's 0-100 and sends the hex color."""
    _mock_video_inputs(aioclient_mock)
    _mock_lighting_switch_put(aioclient_mock)
    await setup_integration(hass, config_entry)

    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, "bosch_shc_camera", unique_id
    )
    assert entity_id is not None

    # First turn the light physically ON — brightness/color changes while off
    # are only pre-staged locally, not sent to the API (see light.py's
    # `was_off and (rgb or brightness)` early-return).
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_BRIGHTNESS: 128,
            ATTR_RGB_COLOR: (255, 0, 0),
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 0)
    # HA brightness 128 -> API round(128*100/255) == 50; the brightness
    # property then converts API->HA via int() truncation (not round()):
    # int(50*255/100) == 127, not 128 — the round-trip is lossy by design.
    assert state.attributes[ATTR_BRIGHTNESS] == int(50 * 255 / 100)

    body = _last_put_body(aioclient_mock, "/lighting/switch")
    assert body[led_key]["brightness"] == 50
    assert body[led_key]["color"] == "#FF0000"
    assert body[led_key]["whiteBalance"] is None


async def test_front_light_turn_on_with_color_temp(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """turn_on with color_temp_kelvin converts Kelvin to the -1.0..1.0 whiteBalance scale."""
    _mock_video_inputs(aioclient_mock)
    _mock_lighting_switch_put(aioclient_mock)
    await setup_integration(hass, config_entry)

    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, "bosch_shc_camera", FRONT_LIGHT_UNIQUE_ID
    )
    assert entity_id is not None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON

    # 3500K is deliberately NOT a clamp boundary (2000-6500K range) — a
    # boundary value like 6500K/2000K would still assert "correctly" even
    # if the whiteBalance conversion formula were broken, since
    # `max(-1.0, min(1.0, wb))` clamps any sufficiently-wrong wb right back
    # to the same boundary value.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP_KELVIN: 3500,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    # Kelvin -> whiteBalance -> Kelvin is lossy (two independent roundings):
    # round((4250-3500)/2250, 2) == 0.33, then int(4250 - 0.33*2250) == 3507.
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3507

    body = _last_put_body(aioclient_mock, "/lighting/switch")
    assert body["frontLightSettings"]["brightness"] == 100
    assert body["frontLightSettings"]["color"] is None
    assert body["frontLightSettings"]["whiteBalance"] == 0.33


@pytest.mark.parametrize(
    ("unique_id", "led_key"),
    [
        (TOP_LED_UNIQUE_ID, "topLedLightSettings"),
        (BOTTOM_LED_UNIQUE_ID, "bottomLedLightSettings"),
        (FRONT_LIGHT_UNIQUE_ID, "frontLightSettings"),
    ],
    ids=["top_led", "bottom_led", "front_light"],
)
async def test_turn_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    unique_id: str,
    led_key: str,
) -> None:
    """turn_off sends brightness=0 for its own light group and the entity reports STATE_OFF."""
    _mock_video_inputs(aioclient_mock)
    _mock_lighting_switch_put(aioclient_mock)
    await setup_integration(hass, config_entry)

    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, "bosch_shc_camera", unique_id
    )
    assert entity_id is not None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    body = _last_put_body(aioclient_mock, "/lighting/switch")
    assert body[led_key]["brightness"] == 0
