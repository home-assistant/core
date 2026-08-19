"""Scene reproduce_state tests for the Color helper."""

import pytest

from homeassistant.components.color.const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    ATTR_HS_COLOR,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_MODE,
    DOMAIN,
    KIND_CHROMATIC,
    KIND_WHITE,
    MODE_CHROMATIC,
)
from homeassistant.components.color.reproduce_state import async_reproduce_states
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry

ENTITY_ID = "color.test_color"


async def _setup_entity(hass: HomeAssistant) -> None:
    """Set up a chromatic entry producing the test entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Color",
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FFFFFF",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is not None


async def test_reproduce_chromatic_hex(hass: HomeAssistant) -> None:
    """Test reproducing a chromatic snapshot from its hex state."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "#00FF00",
        {ATTR_KIND: KIND_CHROMATIC, ATTR_BRIGHTNESS: None},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    _r, g, _b = state.attributes[ATTR_RGB_COLOR]
    assert g > 200
    assert state.attributes[ATTR_BRIGHTNESS] is None


async def test_reproduce_white_with_brightness(hass: HomeAssistant) -> None:
    """Test reproducing a white snapshot restores kelvin and brightness."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "#FFFFFF",
        {ATTR_KIND: KIND_WHITE, ATTR_COLOR_TEMP_KELVIN: 3500, ATTR_BRIGHTNESS: 200},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_KIND] == KIND_WHITE
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3500
    assert state.attributes[ATTR_BRIGHTNESS] == 200


async def test_reproduce_unknown_entity_is_a_noop(hass: HomeAssistant) -> None:
    """Test reproducing a state for a missing entity logs and returns."""
    await _setup_entity(hass)
    snapshot = State("color.does_not_exist", "#00FF00", {ATTR_KIND: KIND_CHROMATIC})
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    assert hass.states.get("color.does_not_exist") is None


@pytest.mark.parametrize(
    ("set_data", "attr"),
    [
        pytest.param({"hex_value": "#37A1FB"}, ATTR_HEX_COLOR, id="hex"),
        pytest.param({"rgb_color": [255, 158, 77]}, ATTR_RGB_COLOR, id="rgb"),
        pytest.param({"hs_color": [200.5, 37.2]}, ATTR_HS_COLOR, id="hs-unrounded"),
        pytest.param(
            {"xy_color": [0.44481, 0.40663]}, ATTR_XY_COLOR, id="xy-unrounded"
        ),
        pytest.param({"color_name": "goldenrod"}, ATTR_RGB_COLOR, id="name"),
    ],
)
async def test_reproduce_round_trips_exact_source(
    hass: HomeAssistant, set_data: dict, attr: str
) -> None:
    """Reproducing a snapshot restores the exact source shape, not a derived view."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        "set_color",
        {"entity_id": ENTITY_ID, **set_data},
        blocking=True,
    )
    await hass.async_block_till_done()
    snapshot_state = hass.states.get(ENTITY_ID)
    snapshot = State(ENTITY_ID, snapshot_state.state, dict(snapshot_state.attributes))

    await hass.services.async_call(
        DOMAIN,
        "set_color",
        {"entity_id": ENTITY_ID, "hex_value": "#123456"},
        blocking=True,
    )
    await hass.async_block_till_done()

    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == snapshot.state
    assert state.attributes[attr] == snapshot.attributes[attr]


async def test_reproduce_corrupt_xy_falls_back_to_hex(hass: HomeAssistant) -> None:
    """A snapshot xy outside the CIE triangle falls back to the hex state."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "#00FF00",
        {ATTR_KIND: KIND_CHROMATIC, ATTR_XY_COLOR: [0.9, 0.9]},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    _r, g, _b = state.attributes[ATTR_RGB_COLOR]
    assert g > 200


async def test_reproduce_hexless_snapshot_uses_xy(hass: HomeAssistant) -> None:
    """A snapshot without a usable hex still restores from its canonical xy."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "unavailable",
        {ATTR_KIND: KIND_CHROMATIC, ATTR_XY_COLOR: [0.1234, 0.4567]},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_XY_COLOR] == [0.1234, 0.4567]


@pytest.mark.parametrize(
    "snapshot_attrs",
    [
        pytest.param(
            {ATTR_KIND: KIND_CHROMATIC, ATTR_XY_COLOR: ["x", "y"]},
            id="non-numeric-xy-falls-back-to-state",
        ),
        pytest.param(
            {ATTR_KIND: KIND_CHROMATIC, ATTR_HS_COLOR: ["h", "s"]},
            id="non-numeric-hs-falls-back-to-state",
        ),
        pytest.param(
            {ATTR_KIND: KIND_CHROMATIC, ATTR_XY_COLOR: [0.1234, 0.4567]},
            id="inconsistent-xy-falls-back-to-state",
        ),
        pytest.param(
            {ATTR_KIND: KIND_WHITE},
            id="white-without-kelvin-restores-as-chromatic",
        ),
    ],
)
async def test_reproduce_defective_snapshots(
    hass: HomeAssistant,
    snapshot_attrs: dict,
) -> None:
    """Defective snapshot attributes fall back to the hex state string."""
    await _setup_entity(hass)
    snapshot = State(ENTITY_ID, "#00FF00", snapshot_attrs)
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == "#00FF00"
    assert state.attributes[ATTR_RGB_COLOR] == [0, 255, 0]


@pytest.mark.parametrize(
    "bad_kelvin",
    [
        pytest.param("hot", id="non-numeric"),
        pytest.param(10**6, id="out-of-range"),
        pytest.param(10**400, id="overflowing"),
    ],
)
async def test_reproduce_corrupt_kelvin_falls_back_to_state(
    hass: HomeAssistant, bad_kelvin: object
) -> None:
    """A white snapshot with an unusable kelvin falls back to the hex state."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "#00FF00",
        {ATTR_KIND: KIND_WHITE, ATTR_COLOR_TEMP_KELVIN: bad_kelvin},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    _r, g, _b = state.attributes[ATTR_RGB_COLOR]
    assert g > 200
    assert state.attributes[ATTR_KIND] == KIND_CHROMATIC


@pytest.mark.parametrize(
    "bad_brightness",
    [
        pytest.param(999, id="out-of-range"),
        pytest.param("dim", id="non-numeric"),
        pytest.param(10**400, id="overflowing"),
    ],
)
async def test_reproduce_corrupt_brightness_is_skipped(
    hass: HomeAssistant, bad_brightness: object
) -> None:
    """An unusable snapshot brightness is skipped; the color still restores."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        "set_brightness",
        {"entity_id": ENTITY_ID, "brightness": 100},
        blocking=True,
    )
    snapshot = State(
        ENTITY_ID,
        "#00FF00",
        {ATTR_KIND: KIND_CHROMATIC, ATTR_BRIGHTNESS: bad_brightness},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    _r, g, _b = state.attributes[ATTR_RGB_COLOR]
    assert g > 200
    assert state.attributes[ATTR_BRIGHTNESS] == 100


async def test_reproduce_overflowing_xy_falls_back_to_state(
    hass: HomeAssistant,
) -> None:
    """A snapshot xy holding an overflowing int falls back to the hex state."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "#00FF00",
        {ATTR_KIND: KIND_CHROMATIC, ATTR_XY_COLOR: [10**400, 0.4]},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    _r, g, _b = state.attributes[ATTR_RGB_COLOR]
    assert g > 200


async def test_reproduce_black_state_does_not_abort_scene(
    hass: HomeAssistant,
) -> None:
    """A #000000 snapshot state is skipped with a warning; the scene continues."""
    await _setup_entity(hass)
    black = State(ENTITY_ID, "#000000", {ATTR_KIND: KIND_CHROMATIC})
    good = State(
        ENTITY_ID,
        "#00FF00",
        {ATTR_KIND: KIND_CHROMATIC, ATTR_BRIGHTNESS: 42},
    )
    await async_reproduce_states(hass, [black, good])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    _r, g, _b = state.attributes[ATTR_RGB_COLOR]
    assert g > 200
    assert state.attributes[ATTR_BRIGHTNESS] == 42
