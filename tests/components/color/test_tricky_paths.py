"""Tests for paths where regressions would silently corrupt user data."""

import math
from typing import Any

import pytest

from homeassistant.components.color.const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_PARAMS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    ATTR_HS_COLOR,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    CONF_INITIAL_BRIGHTNESS,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_KELVIN,
    CONF_INITIAL_MODE,
    DOMAIN,
    FIELD_BRIGHTNESS,
    KIND_CHROMATIC,
    KIND_WHITE,
    MODE_CHROMATIC,
    MODE_WHITE,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
    STATE_SCHEMA_VERSION,
)
from homeassistant.components.color.reproduce_state import async_reproduce_states
from homeassistant.const import ATTR_ENTITY_ID, ATTR_ICON, CONF_ICON, CONF_NAME
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data

ENTITY_ID = "color.test_color"


async def _setup_entity(
    hass: HomeAssistant, data: dict | None = None, title: str = "Test Color"
) -> MockConfigEntry:
    """Set up a config entry and return it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data=data
        or {
            CONF_NAME: title,
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FFFFFF",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_restore_round_trip_preserves_white_kind_and_kelvin(
    hass: HomeAssistant,
) -> None:
    """The extra_data payload must survive a restart round-trip intact."""
    extra = {
        "version": STATE_SCHEMA_VERSION,
        "xy": [0.4599, 0.4106],  # 2700K Planckian xy
        "kind": KIND_WHITE,
        "kelvin": 2700,
        "brightness": 180,
        "source_field": "color_temp_kelvin",
        "source_value": 2700,
    }
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ENTITY_ID, "#FFFFFF", {ATTR_KIND: KIND_WHITE}), extra)],
    )

    await _setup_entity(
        hass,
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#000000",  # deliberately different from restored
        },
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_KIND] == KIND_WHITE
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_BRIGHTNESS] == 180


async def test_restore_round_trip_with_malformed_extra_falls_back(
    hass: HomeAssistant,
) -> None:
    """A garbage extra_data payload should not crash; entity falls back to initial."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ENTITY_ID, "#FFFFFF", {}), {"this": "is not valid"})],
    )

    await _setup_entity(
        hass,
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FF0000",
        },
    )

    state = hass.states.get(ENTITY_ID)
    r, _g, _b = state.attributes[ATTR_RGB_COLOR]
    assert r > 200


@pytest.mark.parametrize(
    ("source_field", "source_value", "attr", "expected"),
    [
        pytest.param("hex_value", "#FF9E4D", ATTR_HEX_COLOR, "#FF9E4D", id="hex-exact"),
        pytest.param(
            "rgb_color", [255, 158, 77], ATTR_RGB_COLOR, [255, 158, 77], id="rgb-exact"
        ),
        pytest.param(
            "hs_color",
            [200.5, 37.2],
            ATTR_HS_COLOR,
            [200.5, 37.2],
            id="hs-exact-unrounded",
        ),
        pytest.param(
            "xy_color",
            [0.44481, 0.40663],
            ATTR_XY_COLOR,
            [0.44481, 0.40663],
            id="xy-exact-unrounded",
        ),
        pytest.param(
            "color_name", "goldenrod", ATTR_RGB_COLOR, [218, 165, 32], id="name-exact"
        ),
    ],
)
async def test_exact_source_persists_across_restart(
    hass: HomeAssistant,
    source_field: str,
    source_value: Any,
    attr: str,
    expected: Any,
) -> None:
    """The exact input echo must survive the restore round-trip."""
    extra = {
        "version": STATE_SCHEMA_VERSION,
        "xy": [0.4, 0.4],
        "kind": KIND_CHROMATIC,
        "kelvin": None,
        "brightness": None,
        "source_field": source_field,
        "source_value": source_value,
    }
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ENTITY_ID, "#0000FF", {}), extra)],
    )

    await _setup_entity(hass)
    assert hass.states.get(ENTITY_ID).attributes[attr] == expected


async def test_restore_migrates_v1_source_hex(hass: HomeAssistant) -> None:
    """A version-1 payload's source_hex becomes the exact hex source."""
    extra = {
        "version": 1,
        "xy": [0.2093, 0.2076],  # what #0050FF normalized to when stored
        "kind": KIND_CHROMATIC,
        "kelvin": None,
        "brightness": None,
        "source_hex": "#0050FF",
    }
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ENTITY_ID, "#0000FF", {}), extra)],
    )

    await _setup_entity(hass)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "#0050FF"
    assert state.attributes[ATTR_HEX_COLOR] == "#0050FF"
    assert state.attributes[ATTR_RGB_COLOR] == [0, 80, 255]


async def test_restore_migrates_v1_white_without_source_hex(
    hass: HomeAssistant,
) -> None:
    """A version-1 white payload falls back to its kelvin as the source."""
    extra = {
        "version": 1,
        "xy": [0.4599, 0.4106],
        "kind": KIND_WHITE,
        "kelvin": 2700,
        "brightness": 42,
        "source_hex": None,
    }
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ENTITY_ID, "#FFFFFF", {ATTR_KIND: KIND_WHITE}), extra)],
    )

    await _setup_entity(hass)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_KIND] == KIND_WHITE
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_BRIGHTNESS] == 42


@pytest.mark.parametrize(
    ("source_field", "source_value"),
    [
        pytest.param("hex_value", "not-a-color", id="bad-hex"),
        pytest.param("hex_value", 123, id="hex-not-a-string"),
        pytest.param("rgb_color", [999, 0, 0], id="rgb-out-of-range"),
        pytest.param("bogus_field", "#0050FF", id="unknown-field"),
        pytest.param("hex_value", None, id="missing-value"),
        pytest.param(None, None, id="missing-source"),
    ],
)
async def test_restore_falls_back_when_source_is_malformed(
    hass: HomeAssistant, source_field: Any, source_value: Any
) -> None:
    """A malformed source only costs the exact echo; the color still restores."""
    extra = {
        "version": STATE_SCHEMA_VERSION,
        "xy": [0.4, 0.4],
        "kind": KIND_CHROMATIC,
        "kelvin": None,
        "brightness": None,
        "source_field": source_field,
        "source_value": source_value,
    }
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ENTITY_ID, "#0000FF", {}), extra)],
    )

    await _setup_entity(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    # The canonical xy becomes the source, echoed exactly.
    assert state.attributes[ATTR_XY_COLOR] == [0.4, 0.4]


async def test_reproduce_state_with_unavailable_skips_color_but_sets_brightness(
    hass: HomeAssistant,
) -> None:
    """If state.state isn't a valid hex, brightness should still apply."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "unavailable",
        {ATTR_KIND: KIND_CHROMATIC, ATTR_BRIGHTNESS: 220},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_BRIGHTNESS] == 220


async def test_reproduce_state_omitting_brightness_attr_does_not_clear(
    hass: HomeAssistant,
) -> None:
    """Snapshot without the brightness attr should NOT clear existing brightness."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_BRIGHTNESS,
        {ATTR_ENTITY_ID: ENTITY_ID, FIELD_BRIGHTNESS: 150},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_BRIGHTNESS] == 150

    snapshot = State(ENTITY_ID, "#00FF00", {ATTR_KIND: KIND_CHROMATIC})
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_BRIGHTNESS] == 150


async def test_options_flow_updates_icon_and_reloads_entity(
    hass: HomeAssistant,
) -> None:
    """Options flow icon changes apply to the entity via the reload listener."""
    entry = await _setup_entity(
        hass,
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FFFFFF",
            CONF_ICON: "mdi:palette",
        },
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_ICON] == "mdi:palette"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ICON: "mdi:lightbulb"}
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_ICON] == "mdi:lightbulb"
    assert hass.states.get(ENTITY_ID).attributes[ATTR_ICON] == "mdi:lightbulb"


async def test_brightness_zero_is_distinct_from_none(hass: HomeAssistant) -> None:
    """A stored brightness of 0 must surface as 0, not as unset."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_BRIGHTNESS,
        {ATTR_ENTITY_ID: ENTITY_ID, FIELD_BRIGHTNESS: 0},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_BRIGHTNESS] == 0
    assert state.attributes[ATTR_COLOR_PARAMS][ATTR_BRIGHTNESS] == 0


async def test_chromatic_override_clears_previous_kelvin(hass: HomeAssistant) -> None:
    """Setting a chromatic color must wipe a previously stored kelvin."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "color_temp_kelvin": 2700},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_KIND] == KIND_WHITE
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2700

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "hex_value": "#FF0000"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_KIND] == KIND_CHROMATIC
    # Chromatic colors don't carry a kelvin — we explicitly emit None rather
    # than a McCamy guess.
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] is None


async def test_service_strips_targeting_keys(hass: HomeAssistant) -> None:
    """Targeting keys like area_id must not leak into normalize()."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "area_id": "some_area",
            "hex_value": "#00FF00",
        },
        blocking=True,
    )
    _r, g, _b = hass.states.get(ENTITY_ID).attributes[ATTR_RGB_COLOR]
    assert g > 200


async def test_set_color_with_brightness_applies_both(hass: HomeAssistant) -> None:
    """Brightness in a set_color call applies alongside the color."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "hex_value": "#0000FF",
            "brightness": 100,
        },
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    _r, _g, b = state.attributes[ATTR_RGB_COLOR]
    assert b > 200
    assert state.attributes[ATTR_BRIGHTNESS] == 100


async def test_initial_brightness_from_config_entry(hass: HomeAssistant) -> None:
    """Initial brightness and kelvin from the config entry flow into the entity."""
    await _setup_entity(
        hass,
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_WHITE,
            CONF_INITIAL_KELVIN: 3000,
            CONF_INITIAL_BRIGHTNESS: 170,
        },
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_BRIGHTNESS] == 170
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3000
    assert state.attributes[ATTR_KIND] == KIND_WHITE


async def test_initial_brightness_garbage_is_safe(hass: HomeAssistant) -> None:
    """Non-int initial brightness from a corrupted entry must not crash setup."""
    await _setup_entity(
        hass,
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FFFFFF",
            CONF_INITIAL_BRIGHTNESS: "not-a-number",
        },
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_BRIGHTNESS] is None


async def test_hex_input_is_the_state_exactly(hass: HomeAssistant) -> None:
    """A typed hex is the state and hex_color, normalized to uppercase only."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "hex_value": "#0050ff"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == "#0050FF"
    assert state.attributes[ATTR_HEX_COLOR] == "#0050FF"


async def test_derived_shapes_stay_rounded(hass: HomeAssistant) -> None:
    """Non-source shapes keep the display rounding (hs 2 dp, xy 4 dp)."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "hex_value": "#0050FF"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    hue, sat = state.attributes[ATTR_HS_COLOR]
    assert hue == round(hue, 2)
    assert sat == round(sat, 2)
    x, y = state.attributes[ATTR_XY_COLOR]
    assert x == round(x, 4)
    assert y == round(y, 4)


async def test_color_name_resolves_exact_table_rgb(hass: HomeAssistant) -> None:
    """Named colors resolve to the exact CSS3 table triple."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "color_name": "red"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    # CSS3 "red" is exactly #FF0000 — no gamut math involved.
    assert state.attributes[ATTR_HEX_COLOR] == "#FF0000"
    assert state.attributes[ATTR_RGB_COLOR] == [255, 0, 0]


@pytest.mark.parametrize(
    "extra",
    [
        {"version": STATE_SCHEMA_VERSION, "xy": [], "kind": KIND_CHROMATIC},
        {"version": STATE_SCHEMA_VERSION, "xy": [0.4], "kind": KIND_CHROMATIC},
        {
            "version": STATE_SCHEMA_VERSION,
            "xy": [math.nan, 0.4],
            "kind": KIND_CHROMATIC,
        },
        {
            "version": STATE_SCHEMA_VERSION,
            "xy": [math.inf, 0.4],
            "kind": KIND_CHROMATIC,
        },
        {"version": STATE_SCHEMA_VERSION, "xy": [0.4, 0.4], "kind": "bogus"},
        {"version": 99, "xy": [0.4, 0.4], "kind": KIND_CHROMATIC},
        {"xy": [0.4, 0.4], "kind": KIND_CHROMATIC},
        {"version": STATE_SCHEMA_VERSION, "xy": [0.0, 0.0], "kind": KIND_CHROMATIC},
        {"version": STATE_SCHEMA_VERSION, "xy": [0.7, 0.7], "kind": KIND_CHROMATIC},
        {"version": STATE_SCHEMA_VERSION, "xy": [0.35, 0.35], "kind": KIND_WHITE},
        {
            "version": STATE_SCHEMA_VERSION,
            "xy": [0.35, 0.35],
            "kind": KIND_WHITE,
            "kelvin": 100,
        },
        {
            "version": STATE_SCHEMA_VERSION,
            "xy": [0.4, 0.4],
            "kind": KIND_CHROMATIC,
            "brightness": 999,
        },
        {
            "version": STATE_SCHEMA_VERSION,
            "xy": [0.4, 0.4],
            "kind": KIND_CHROMATIC,
            "kelvin": 5000,
        },
        {"version": math.inf, "xy": [0.4, 0.4], "kind": KIND_CHROMATIC},
        {
            "version": STATE_SCHEMA_VERSION,
            "xy": [0.4, 0.4],
            "kind": KIND_CHROMATIC,
            "brightness": math.inf,
        },
    ],
)
async def test_restore_rejects_invalid_payload_shapes(
    hass: HomeAssistant, extra: dict
) -> None:
    """Short, non-finite, or wrong-kind restore payloads fall back to initial."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ENTITY_ID, "#FFFFFF", {}), extra)],
    )

    await _setup_entity(
        hass,
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FF0000",
        },
    )

    state = hass.states.get(ENTITY_ID)
    r, _g, _b = state.attributes[ATTR_RGB_COLOR]
    assert r > 200
