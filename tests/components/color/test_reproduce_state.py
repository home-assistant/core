"""Scene reproduce_state tests for the Color helper."""

import pytest

from homeassistant.components.color.const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_SOURCE_HEX,
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


async def test_reproduce_chromatic_prefers_xy_attribute(
    hass: HomeAssistant,
) -> None:
    """A snapshot's canonical xy wins over the derived (lossy) hex state."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "#00FF00",
        {
            ATTR_KIND: KIND_CHROMATIC,
            ATTR_XY_COLOR: [0.1234, 0.4567],
            ATTR_BRIGHTNESS: None,
        },
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_XY_COLOR] == [0.1234, 0.4567]


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


async def test_reproduce_preserves_source_hex(hass: HomeAssistant) -> None:
    """A snapshot whose source hex matches the state restores via hex."""
    await _setup_entity(hass)
    await hass.services.async_call(
        DOMAIN,
        "set_color",
        {"entity_id": ENTITY_ID, "hex_value": "#37A1FB"},
        blocking=True,
    )
    await hass.async_block_till_done()
    snapshot_state = hass.states.get(ENTITY_ID)
    snapshot = State(ENTITY_ID, snapshot_state.state, dict(snapshot_state.attributes))

    await hass.services.async_call(
        DOMAIN,
        "set_color",
        {"entity_id": ENTITY_ID, "hex_value": "#FF0000"},
        blocking=True,
    )
    await hass.async_block_till_done()

    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == snapshot.state
    assert state.attributes[ATTR_SOURCE_HEX] == snapshot.attributes[ATTR_SOURCE_HEX]


@pytest.mark.parametrize(
    ("snapshot_attrs", "expected_source_hex"),
    [
        pytest.param(
            {ATTR_KIND: KIND_CHROMATIC, ATTR_XY_COLOR: ["x", "y"]},
            "#00FF00",
            id="non-numeric-xy-falls-back-to-state",
        ),
        pytest.param(
            {ATTR_KIND: KIND_CHROMATIC, ATTR_SOURCE_HEX: "#000000"},
            "#00FF00",
            id="black-source-hex-falls-back-to-state",
        ),
        pytest.param(
            {ATTR_KIND: KIND_CHROMATIC, ATTR_SOURCE_HEX: "#00FF00"},
            "#00FF00",
            id="source-hex-without-xy-restores-source",
        ),
        pytest.param(
            {
                ATTR_KIND: KIND_CHROMATIC,
                ATTR_SOURCE_HEX: "#00FF00",
                ATTR_XY_COLOR: ["x", "y"],
            },
            "#00FF00",
            id="source-hex-with-corrupt-xy-falls-back-to-state",
        ),
        pytest.param(
            {ATTR_KIND: KIND_WHITE},
            "#00FF00",
            id="white-without-kelvin-restores-as-chromatic",
        ),
    ],
)
async def test_reproduce_defective_snapshots(
    hass: HomeAssistant,
    snapshot_attrs: dict,
    expected_source_hex: str | None,
) -> None:
    """Defective snapshot attributes fall back to the hex state string."""
    await _setup_entity(hass)
    snapshot = State(ENTITY_ID, "#00FF00", snapshot_attrs)
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    _r, g, _b = state.attributes[ATTR_RGB_COLOR]
    assert g > 200
    assert state.attributes[ATTR_SOURCE_HEX] == expected_source_hex
