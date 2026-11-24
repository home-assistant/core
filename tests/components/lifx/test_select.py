"""Tests for the LIFX select platform."""

from collections.abc import Callable
from typing import Any

from lifx import LifxError, Theme, ThemeLibrary
from lifx.devices.paint_record import PaintKind
import pytest

from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.const import LIFXService, LIFXServiceArgument
from homeassistant.components.lifx.util import THEME_OPTIONS, THEME_SELECT_OPTIONS
from homeassistant.components.select import ATTR_OPTIONS, DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import SERIAL, async_setup_lifx_entry, async_trigger_update
from .helpers import (
    INFRARED_SELECT_ENTITY_ID,
    MockDevice,
    clear_paint_record,
    create_mock_ceiling_light,
    create_mock_infrared_light,
    create_mock_light,
    create_mock_matrix_light,
    create_mock_mirror_light,
    create_mock_multizone_light,
    record_paint,
)

LIGHT_ENTITY_ID = "light.my_group_my_bulb"
THEME_ENTITY_ID = "select.my_group_my_bulb_theme"
MOOD_ENTITY_ID = "select.my_group_my_bulb_mood"


def _record_theme(device: MockDevice) -> None:
    """Make painting a theme leave the record the library keeps."""

    async def apply_theme(theme: Theme, **_kwargs: Any) -> None:
        record_paint(device, "theme", theme.slug)

    device.apply_theme.side_effect = apply_theme


async def test_theme_select(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test picking a theme paints it and shows what the library records."""
    device = create_mock_multizone_light()
    _record_theme(device)
    await async_setup_lifx_entry(hass, device)

    entity = entity_registry.async_get(THEME_ENTITY_ID)
    assert entity
    assert not entity.disabled
    state = hass.states.get(THEME_ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_OPTIONS] == THEME_SELECT_OPTIONS

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: THEME_ENTITY_ID, "option": "intense"},
        blocking=True,
    )

    device.apply_theme.assert_awaited_once()
    applied_theme = device.apply_theme.await_args.args[0]
    assert applied_theme.colors == ThemeLibrary.get("intense").colors
    state = hass.states.get(THEME_ENTITY_ID)
    assert state
    assert state.state == "intense"

    await async_trigger_update(hass)
    state = hass.states.get(THEME_ENTITY_ID)
    assert state
    assert state.state == "intense"


@pytest.mark.parametrize(
    ("alias", "successor"),
    [
        ("aurora_borealis", "aurora"),
        ("energising", "energizing"),
        ("forest", "forrest"),
    ],
)
async def test_theme_select_accepts_a_renamed_theme(
    hass: HomeAssistant, alias: str, successor: str
) -> None:
    """Test a theme the select offered before its rename still paints its successor.

    Automations written before the rename pick the alias, so the select keeps it.
    """
    device = create_mock_multizone_light()
    _record_theme(device)
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: THEME_ENTITY_ID, "option": alias},
        blocking=True,
    )

    assert device.apply_theme.await_args.args[0].slug == successor
    state = hass.states.get(THEME_ENTITY_ID)
    assert state
    assert state.state == successor


async def test_theme_select_clears_when_the_light_changes(
    hass: HomeAssistant,
) -> None:
    """Test the select goes unknown once the library no longer sees the theme."""
    device = create_mock_multizone_light()
    record_paint(device, "theme", "intense")
    await async_setup_lifx_entry(hass, device)
    state = hass.states.get(THEME_ENTITY_ID)
    assert state
    assert state.state == "intense"

    # A poll that finds any zone changed ends the library's record
    clear_paint_record(device)
    await async_trigger_update(hass)

    state = hass.states.get(THEME_ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_theme_select_follows_the_paint_theme_action(
    hass: HomeAssistant,
) -> None:
    """Test a theme painted by the paint_theme action shows on the select."""
    device = create_mock_multizone_light()
    _record_theme(device)
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        LIFXService.PAINT_THEME,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID, LIFXServiceArgument.THEME: "halloween"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(THEME_ENTITY_ID)
    assert state
    assert state.state == "halloween"


async def test_mood_select_applies_and_shows_the_library_record(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test picking a Mood applies it, and the select shows what the library reports."""
    device = create_mock_multizone_light()
    await async_setup_lifx_entry(hass, device)

    entity = entity_registry.async_get(MOOD_ENTITY_ID)
    assert entity
    assert entity.unique_id == f"{SERIAL}_mood"
    state = hass.states.get(MOOD_ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_OPTIONS] == THEME_OPTIONS

    async def apply_mood(theme: Theme) -> None:
        record_paint(device, "mood", theme.slug)

    device.apply_mood.side_effect = apply_mood
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: MOOD_ENTITY_ID, "option": "dream"},
        blocking=True,
    )

    device.apply_mood.assert_awaited_once()
    assert device.apply_mood.await_args.args[0].slug == "dream"
    state = hass.states.get(MOOD_ENTITY_ID)
    assert state
    assert state.state == "dream"

    # The library drops the record once a refresh finds the light changed
    clear_paint_record(device)
    await async_trigger_update(hass)
    state = hass.states.get(MOOD_ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("option_entity_id", "option", "method", "kind", "cleared_entity_id", "shown"),
    [
        pytest.param(
            MOOD_ENTITY_ID,
            "dream",
            "apply_mood",
            "mood",
            THEME_ENTITY_ID,
            "theme",
            id="mood",
        ),
        pytest.param(
            THEME_ENTITY_ID,
            "intense",
            "apply_theme",
            "theme",
            MOOD_ENTITY_ID,
            "mood",
            id="theme",
        ),
    ],
)
async def test_picking_one_select_blanks_the_other_at_once(
    hass: HomeAssistant,
    option_entity_id: str,
    option: str,
    method: str,
    kind: PaintKind,
    cleared_entity_id: str,
    shown: PaintKind,
) -> None:
    """Test a Mood replaces a theme on the selects straight away, and the reverse.

    A light has at most one of the two, and the library swaps them as it
    paints, so the other select must not wait for the next poll.
    """
    device = create_mock_multizone_light()
    record_paint(device, shown, "autumn")
    await async_setup_lifx_entry(hass, device)
    state = hass.states.get(cleared_entity_id)
    assert state
    assert state.state == "autumn"

    async def paint(theme: Theme, **_kwargs: Any) -> None:
        record_paint(device, kind, theme.slug)

    getattr(device, method).side_effect = paint
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: option_entity_id, "option": option},
        blocking=True,
    )

    state = hass.states.get(cleared_entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(option_entity_id)
    assert state
    assert state.state == option


@pytest.mark.parametrize(
    ("factory", "expected"),
    [
        pytest.param(create_mock_light, False, id="bulb"),
        pytest.param(create_mock_multizone_light, True, id="multizone"),
        pytest.param(create_mock_matrix_light, True, id="matrix"),
        pytest.param(create_mock_ceiling_light, True, id="ceiling"),
        pytest.param(create_mock_mirror_light, True, id="mirror"),
    ],
)
async def test_mood_select_only_on_zoned_lights(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], MockDevice],
    expected: bool,
) -> None:
    """Test only strips and matrix lights get a Mood select.

    One colour is too little for the library to tell which Mood a bulb shows.
    """
    await async_setup_lifx_entry(hass, factory())

    assert (
        entity_registry.async_get_entity_id(SELECT_DOMAIN, DOMAIN, f"{SERIAL}_mood")
        is not None
    ) is expected


async def test_theme_select_shows_the_action_paint_before_the_refresh(
    hass: HomeAssistant,
) -> None:
    """Test the select shows a painted theme while the refresh still waits.

    The library's refresh waits for a long transition to finish, so the select
    must not wait for it.
    """
    device = create_mock_multizone_light()
    _record_theme(device)
    await async_setup_lifx_entry(hass, device)
    seen: list[str] = []

    async def refresh_state() -> None:
        state = hass.states.get(THEME_ENTITY_ID)
        assert state
        seen.append(state.state)

    device.refresh_state.side_effect = refresh_state
    await hass.services.async_call(
        DOMAIN,
        LIFXService.PAINT_THEME,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID, LIFXServiceArgument.THEME: "halloween"},
        blocking=True,
    )

    assert seen == ["halloween"]


async def test_mood_select_refreshes_the_light(hass: HomeAssistant) -> None:
    """Test picking a Mood refreshes the light, which the Mood may turn on."""
    device = create_mock_multizone_light()
    await async_setup_lifx_entry(hass, device)
    device.refresh_state.reset_mock()

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: MOOD_ENTITY_ID, "option": "dream"},
        blocking=True,
    )

    device.refresh_state.assert_awaited_once()


@pytest.mark.parametrize(
    ("option", "level", "refreshed_level"),
    [
        pytest.param("Disabled", 0.0, 0 / 65535, id="disabled"),
        pytest.param("25%", 0.25, 16383 / 65535, id="quarter"),
        pytest.param("50%", 0.5, 32767 / 65535, id="half"),
        pytest.param("100%", 1.0, 65535 / 65535, id="full"),
    ],
)
async def test_infrared_brightness(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    option: str,
    level: float,
    refreshed_level: float,
) -> None:
    """Test typed infrared levels map to unchanged option labels."""
    device = create_mock_infrared_light()
    await async_setup_lifx_entry(hass, device)
    entity_id = INFRARED_SELECT_ENTITY_ID

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == f"{SERIAL}_infrared_brightness"

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": option},
        blocking=True,
    )
    device.set_infrared.assert_awaited_once_with(level)

    device.state.infrared = refreshed_level
    await async_trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == option


@pytest.mark.parametrize(
    ("factory", "method", "entity_id", "option"),
    [
        pytest.param(
            create_mock_infrared_light,
            "set_infrared",
            INFRARED_SELECT_ENTITY_ID,
            "50%",
            id="infrared_brightness",
        ),
        pytest.param(
            create_mock_multizone_light,
            "apply_theme",
            THEME_ENTITY_ID,
            "intense",
            id="theme",
        ),
        pytest.param(
            create_mock_multizone_light,
            "apply_mood",
            MOOD_ENTITY_ID,
            "dream",
            id="mood",
        ),
    ],
)
async def test_select_library_error_becomes_home_assistant_error(
    hass: HomeAssistant,
    factory: Callable[[], MockDevice],
    method: str,
    entity_id: str,
    option: str,
) -> None:
    """Test a library failure surfaces as a Home Assistant error."""
    device = factory()
    await async_setup_lifx_entry(hass, device)
    getattr(device, method).side_effect = LifxError("device unreachable")

    with pytest.raises(HomeAssistantError, match="device unreachable"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: entity_id, "option": option},
            blocking=True,
        )
