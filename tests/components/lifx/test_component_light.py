"""Tests for the LIFX component light entities."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, call

from lifx import HSBK, CeilingLight, Device, LifxError
import pytest

from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.const import (
    ATTR_INFRARED,
    ATTR_POWER,
    ATTR_ZONES,
    SERVICE_EFFECT_COLORSWEEP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_PULSE,
    SERVICE_SET_HEV_CYCLE_STATE,
    SERVICE_SET_STATE,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_STEP_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY

from . import (
    SERIAL,
    async_enable_components,
    async_setup_lifx_entry,
    async_trigger_update,
)
from .helpers import (
    create_mock_matrix_light,
    create_reference_ceiling_light,
    create_reference_mirror_light,
)

from tests.common import (
    async_mock_restore_state_shutdown_restart,
    async_mock_service,
    mock_restore_cache_with_extra_data,
)

CEILING_KEYS = ("uplight", "downlight")
MIRROR_KEYS = ("front", "back")

MAIN_ENTITY_ID = "light.my_group_my_bulb"

COMPONENTS = [
    pytest.param(create_reference_ceiling_light, CEILING_KEYS, id="ceiling"),
    pytest.param(create_reference_mirror_light, MIRROR_KEYS, id="mirror"),
]

ON_OFF = [
    pytest.param(
        create_reference_ceiling_light,
        CEILING_KEYS,
        "uplight",
        "turn_uplight_on",
        "turn_uplight_off",
        id="uplight",
    ),
    pytest.param(
        create_reference_ceiling_light,
        CEILING_KEYS,
        "downlight",
        "turn_downlight_on",
        "turn_downlight_off",
        id="downlight",
    ),
    pytest.param(
        create_reference_mirror_light,
        MIRROR_KEYS,
        "front",
        "turn_front_on",
        "turn_front_off",
        id="front",
    ),
    pytest.param(
        create_reference_mirror_light,
        MIRROR_KEYS,
        "back",
        "turn_back_on",
        "turn_back_off",
        id="back",
    ),
]

MANY_ZONE = [
    pytest.param(
        create_reference_ceiling_light,
        CEILING_KEYS,
        "downlight",
        "downlight_colors",
        "turn_downlight_on",
        id="downlight",
    ),
    pytest.param(
        create_reference_mirror_light,
        MIRROR_KEYS,
        "back",
        "back_colors",
        "turn_back_on",
        id="back",
    ),
]


def entity_id_for(key: str) -> str:
    """Return the entity ID of a component of the test device."""
    return f"light.my_group_my_bulb_{key}"


async def _setup_components(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
) -> Device:
    """Set up a device with its component entities enabled."""
    device = factory()
    entry = await async_setup_lifx_entry(hass, device)
    await async_enable_components(hass, entry, entity_registry, device, keys)
    return device


async def _call(
    hass: HomeAssistant, domain: str, service: str, key: str, **data: Any
) -> None:
    """Call an action on one component entity."""
    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id_for(key), **data}, blocking=True
    )


@pytest.mark.parametrize(("factory", "keys"), COMPONENTS)
async def test_components_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
) -> None:
    """Test component entities are registered but disabled by default."""
    await async_setup_lifx_entry(hass, factory())

    for key in keys:
        entry = entity_registry.async_get(entity_id_for(key))
        assert entry is not None
        assert entry.unique_id == f"{SERIAL}_{key}"
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id_for(key)) is None


@pytest.mark.parametrize(("factory", "keys"), COMPONENTS)
async def test_components_report_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
) -> None:
    """Test enabled component entities report brightness and colour temperature."""
    device = factory()
    entry = await async_setup_lifx_entry(hass, device)
    await async_enable_components(hass, entry, entity_registry, device, keys)

    for key in keys:
        state = hass.states.get(entity_id_for(key))
        assert state is not None
        assert state.state == STATE_ON
        assert state.attributes[ATTR_BRIGHTNESS] == 128
        assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3500
        assert state.attributes[ATTR_COLOR_MODE] is ColorMode.COLOR_TEMP
        assert ATTR_EFFECT_LIST not in state.attributes


@pytest.mark.parametrize(
    ("factory", "keys", "field"),
    [
        pytest.param(
            create_reference_ceiling_light,
            ("downlight", "uplight"),
            "downlight_colors",
            id="downlight",
        ),
        pytest.param(
            create_reference_mirror_light, MIRROR_KEYS, "front_colors", id="front"
        ),
    ],
)
async def test_multizone_component_reports_average_color(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
    field: str,
) -> None:
    """Test a many-zone component reports the average colour of its zones."""
    device = factory()
    entry = await async_setup_lifx_entry(hass, device)
    await async_enable_components(hass, entry, entity_registry, device, keys)

    zone_count = len(getattr(device.state, field))
    # The first and last zones differ from the rest in opposite directions, so
    # only an average of every zone comes out at hue 120 and 75% brightness
    setattr(
        device.state,
        field,
        [
            HSBK(90.0, 0.5, 0.5, 3500),
            *[HSBK(120.0, 0.5, 0.75, 3500)] * (zone_count - 2),
            HSBK(150.0, 0.5, 1.0, 3500),
        ],
    )
    await async_trigger_update(hass)

    state = hass.states.get(entity_id_for(keys[0]))
    assert state is not None
    assert state.attributes[ATTR_COLOR_MODE] is ColorMode.HS
    assert state.attributes[ATTR_HS_COLOR] == pytest.approx((120.0, 50.0), abs=0.1)
    assert state.attributes[ATTR_BRIGHTNESS] == 191


@pytest.mark.parametrize(
    ("factory", "keys", "fields"),
    [
        pytest.param(
            create_reference_ceiling_light,
            CEILING_KEYS,
            ("uplight_is_on", "downlight_is_on"),
            id="ceiling",
        ),
        pytest.param(
            create_reference_mirror_light,
            MIRROR_KEYS,
            ("front_is_on", "back_is_on"),
            id="mirror",
        ),
    ],
)
async def test_components_report_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
    fields: tuple[str, ...],
) -> None:
    """Test component entities follow the library's on and off state."""
    device = factory()
    entry = await async_setup_lifx_entry(hass, device)
    await async_enable_components(hass, entry, entity_registry, device, keys)

    for field in fields:
        setattr(device.state, field, False)
    await async_trigger_update(hass)

    for key in keys:
        assert hass.states.get(entity_id_for(key)).state == STATE_OFF


async def test_plain_matrix_has_no_components(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a matrix light that is neither a Ceiling nor a Mirror gets none."""
    await async_setup_lifx_entry(hass, create_mock_matrix_light())

    for key in (*CEILING_KEYS, *MIRROR_KEYS):
        assert (
            entity_registry.async_get_entity_id(
                Platform.LIGHT, DOMAIN, f"{SERIAL}_{key}"
            )
            is None
        )


@pytest.mark.parametrize(
    ("is_on", "expected"),
    [
        pytest.param(False, [call(None, 0.0)], id="off"),
        pytest.param(True, [], id="already-on"),
    ],
)
@pytest.mark.parametrize(("factory", "keys", "key", "turn_on", "turn_off"), ON_OFF)
async def test_turn_on_without_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
    key: str,
    turn_on: str,
    turn_off: str,
    is_on: bool,
    expected: list[Any],
) -> None:
    """Test a bare turn on lets the library work the colour out, if it is off.

    An on component is left alone: turning it on again would repaint it
    from the library's remembered colours.
    """
    device = await _setup_components(hass, entity_registry, factory, keys)
    setattr(device.state, f"{key}_is_on", is_on)
    await async_trigger_update(hass)

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, key)

    assert getattr(device, turn_on).await_args_list == expected


async def test_uplight_turn_on_with_brightness(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a brightness change keeps the uplight's colour temperature."""
    device = await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, "uplight", brightness=255)

    device.turn_uplight_on.assert_awaited_once_with(HSBK(0.0, 0.0, 1.0, 3500), 0.0)


@pytest.mark.parametrize(("factory", "keys", "key", "field", "turn_on"), MANY_ZONE)
async def test_hue_change_keeps_each_zone_distinct(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
    key: str,
    field: str,
    turn_on: str,
) -> None:
    """Test a hue change leaves every zone at its own brightness."""
    device = await _setup_components(hass, entity_registry, factory, keys)
    setattr(
        device.state,
        field,
        [HSBK(0.0, 0.0, 0.25, 3500), HSBK(0.0, 0.0, 0.75, 3500)],
    )
    await async_trigger_update(hass)

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, key, hs_color=(120.0, 50.0))

    colors, _ = getattr(device, turn_on).await_args.args
    assert [color.brightness for color in colors] == [0.25, 0.75]
    assert {color.hue for color in colors} == {120.0}


@pytest.mark.parametrize(
    ("stored", "expected_brightness"),
    [
        pytest.param(None, 0.6, id="partner-brightness"),
        pytest.param([HSBK(0.0, 0.0, 0.3, 3500)] * 2, 0.3, id="remembered"),
        pytest.param([HSBK(0.0, 0.0, 0.0, 3500)] * 2, 0.6, id="remembered-dark"),
    ],
)
async def test_hue_change_on_an_off_component(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    stored: list[HSBK] | None,
    expected_brightness: float,
) -> None:
    """Test a hue-only change lights an off component at a real brightness."""
    device = await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )
    device.state.downlight_is_on = False
    device.state.downlight_colors = [HSBK(0.0, 0.0, 0.0, 3500)] * 2
    device.state.stored_downlight_colors = stored
    device.state.uplight_color = HSBK(0.0, 0.0, 0.6, 3500)
    await async_trigger_update(hass)

    await _call(
        hass, LIGHT_DOMAIN, SERVICE_TURN_ON, "downlight", hs_color=(120.0, 50.0)
    )

    colors, _ = device.turn_downlight_on.await_args.args
    assert [color.brightness for color in colors] == pytest.approx(
        [expected_brightness] * len(colors), abs=0.01
    )
    assert {color.hue for color in colors} == {120.0}


@pytest.mark.parametrize(
    ("data", "extra_reads"),
    [
        pytest.param({"hs_color": (120.0, 50.0)}, 1, id="partial"),
        pytest.param(
            {"brightness": 200, "color_temp_kelvin": 4000}, 0, id="overwrites"
        ),
    ],
)
async def test_turn_on_reads_before_a_partial_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    data: dict[str, Any],
    extra_reads: int,
) -> None:
    """Test only a change that keeps part of the colour reads the device first."""
    device = await _setup_components(
        hass, entity_registry, create_reference_mirror_light, MIRROR_KEYS
    )
    device.refresh_state.reset_mock()

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, "front", **data)

    # The coordinator's request_refresh_debouncer runs immediately unless it
    # is inside its cooldown window, so the write itself always reads once
    # more; only a partial change reads an extra time first, to merge onto it
    assert device.refresh_state.await_count == 1 + extra_reads


async def test_turn_on_refuses_to_merge_over_stale_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a partial change is refused when the device cannot be read."""
    device = await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )
    device.refresh_state.side_effect = LifxError("unreachable")

    with pytest.raises(HomeAssistantError) as err:
        await _call(
            hass, LIGHT_DOMAIN, SERVICE_TURN_ON, "downlight", hs_color=(1.0, 1.0)
        )
    assert err.value.translation_key == "cannot_read_state"
    device.turn_downlight_on.assert_not_awaited()


@pytest.mark.parametrize(("factory", "keys", "key", "turn_on", "turn_off"), ON_OFF)
async def test_turn_on_with_zero_brightness_turns_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
    key: str,
    turn_on: str,
    turn_off: str,
) -> None:
    """Test core redirects a turn on at zero brightness to turning the component off."""
    device = await _setup_components(hass, entity_registry, factory, keys)

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, key, brightness=0)

    getattr(device, turn_on).assert_not_awaited()
    getattr(device, turn_off).assert_awaited_once_with(None, 0.0)


async def test_turn_on_with_a_brightness_step(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a relative step resolves against the component's own brightness."""
    device = await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )

    await _call(
        hass,
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        "uplight",
        **{ATTR_BRIGHTNESS_STEP_PCT: 10},
    )

    color, _ = device.turn_uplight_on.await_args.args
    assert color.brightness == pytest.approx(0.6, abs=0.01)


@pytest.mark.parametrize(("factory", "keys", "key", "turn_on", "turn_off"), ON_OFF)
async def test_turn_off_with_a_transition(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
    key: str,
    turn_on: str,
    turn_off: str,
) -> None:
    """Test a transition is passed through to the component turn off."""
    device = await _setup_components(hass, entity_registry, factory, keys)

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF, key, **{ATTR_TRANSITION: 3})

    getattr(device, turn_off).assert_awaited_once_with(None, 3.0)


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param(SERVICE_TURN_ON, "turn_front_on", id="turn-on"),
        pytest.param(SERVICE_TURN_OFF, "turn_front_off", id="turn-off"),
    ],
)
async def test_device_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service: str,
    method: str,
) -> None:
    """Test a library failure surfaces as a Home Assistant error."""
    device = await _setup_components(
        hass, entity_registry, create_reference_mirror_light, MIRROR_KEYS
    )
    # Off, so that a bare turn on writes to the device
    device.state.front_is_on = False
    await async_trigger_update(hass)
    getattr(device, method).side_effect = LifxError("boom")

    with pytest.raises(HomeAssistantError, match="boom"):
        await _call(hass, LIGHT_DOMAIN, service, "front")


async def test_write_stops_a_software_effect(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_effect_conductor: MagicMock,
) -> None:
    """Test a component write first stops a software effect on the device."""
    device = await _setup_components(
        hass, entity_registry, create_reference_mirror_light, MIRROR_KEYS
    )
    mock_effect_conductor.stop.reset_mock()

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF, "front")

    mock_effect_conductor.stop.assert_awaited_once_with([device])
    device.turn_front_off.assert_awaited_once()


async def test_stopping_a_software_effect_can_fail(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_effect_conductor: MagicMock,
) -> None:
    """Test a failure to stop a software effect is reported and nothing is written."""
    device = await _setup_components(
        hass, entity_registry, create_reference_mirror_light, MIRROR_KEYS
    )
    mock_effect_conductor.stop.side_effect = LifxError("restore boom")

    with pytest.raises(HomeAssistantError, match="restore boom"):
        await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF, "front")
    device.turn_front_off.assert_not_awaited()


@pytest.mark.parametrize(
    ("is_on", "data", "turn_on_calls", "turn_off_calls"),
    [
        pytest.param(False, {ATTR_POWER: True}, 1, 0, id="power-on"),
        pytest.param(True, {ATTR_POWER: False}, 0, 1, id="power-off"),
        pytest.param(True, {"brightness": 200}, 1, 0, id="no-power-while-on"),
        pytest.param(False, {"brightness": 200}, 0, 1, id="no-power-while-off"),
        pytest.param(False, {}, 0, 0, id="nothing-to-do-while-off"),
        pytest.param(
            False,
            {ATTR_BRIGHTNESS_STEP_PCT: 20},
            0,
            1,
            id="brightness-step-while-off",
        ),
    ],
)
async def test_set_state_power(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    is_on: bool,
    data: dict[str, Any],
    turn_on_calls: int,
    turn_off_calls: int,
) -> None:
    """Test lifx.set_state turns a component on or off only when asked."""
    device = await _setup_components(
        hass, entity_registry, create_reference_mirror_light, MIRROR_KEYS
    )
    device.state.front_is_on = is_on
    await async_trigger_update(hass)

    await _call(hass, DOMAIN, SERVICE_SET_STATE, "front", **data)

    assert device.turn_front_on.await_count == turn_on_calls
    assert device.turn_front_off.await_count == turn_off_calls


async def test_set_state_zero_brightness_turns_off(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test lifx.set_state asking to turn on at zero brightness turns off.

    Unlike light.turn_on, the light platform does not intercept this for
    lifx.set_state, so the component itself has to redirect it.
    """
    device = await _setup_components(
        hass, entity_registry, create_reference_mirror_light, MIRROR_KEYS
    )

    await _call(
        hass, DOMAIN, SERVICE_SET_STATE, "front", **{ATTR_POWER: True, "brightness": 0}
    )

    device.turn_front_on.assert_not_awaited()
    device.turn_front_off.assert_awaited_once_with(None, 0.0)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="no-power"),
        pytest.param({ATTR_POWER: False}, id="power-off"),
    ],
)
async def test_set_state_remembers_a_color_while_off(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, data: dict[str, Any]
) -> None:
    """Test a colour set with the component left off is kept for its next turn on."""
    device = await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )
    device.state.downlight_is_on = False
    device.state.downlight_colors = [HSBK(0.0, 0.0, 0.0, 3500)] * 2
    device.state.stored_downlight_colors = None
    await async_trigger_update(hass)

    await _call(
        hass,
        DOMAIN,
        SERVICE_SET_STATE,
        "downlight",
        hs_color=(240.0, 100.0),
        **data,
    )

    device.turn_downlight_on.assert_not_awaited()
    colors, duration = device.turn_downlight_off.await_args.args
    assert {color.hue for color in colors} == {240.0}
    assert {color.brightness for color in colors} == {0.5}
    assert duration == 0.0


async def test_set_state_ignores_zones(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test multizone zones do not narrow a change to a matrix component."""
    device = await _setup_components(
        hass, entity_registry, create_reference_mirror_light, MIRROR_KEYS
    )

    await _call(
        hass,
        DOMAIN,
        SERVICE_SET_STATE,
        "back",
        hs_color=(120.0, 100.0),
        **{ATTR_ZONES: [0, 2]},
    )

    colors, _ = device.turn_back_on.await_args.args
    assert {color.hue for color in colors} == {120.0}


@pytest.mark.parametrize(
    ("factory", "keys", "effect"),
    [
        pytest.param(
            create_reference_ceiling_light,
            CEILING_KEYS,
            SERVICE_EFFECT_FLAME,
            id="flame",
        ),
        pytest.param(
            create_reference_mirror_light,
            MIRROR_KEYS,
            SERVICE_EFFECT_COLORSWEEP,
            id="color-sweep",
        ),
    ],
)
async def test_set_state_forwards_a_firmware_effect(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
    effect: str,
) -> None:
    """Test a firmware effect runs on the whole device through its main light."""
    await _setup_components(hass, entity_registry, factory, keys)
    calls = async_mock_service(hass, DOMAIN, effect)

    await _call(hass, DOMAIN, SERVICE_SET_STATE, keys[0], **{ATTR_EFFECT: effect})

    assert [call.data[ATTR_ENTITY_ID] for call in calls] == [MAIN_ENTITY_ID]


@pytest.mark.parametrize(
    ("service", "data", "translation_key"),
    [
        pytest.param(
            SERVICE_SET_STATE,
            {ATTR_EFFECT: SERVICE_EFFECT_PULSE},
            "component_software_effect",
            id="software-effect",
        ),
        pytest.param(
            SERVICE_SET_STATE, {ATTR_INFRARED: 10}, "no_infrared", id="infrared"
        ),
        pytest.param(
            SERVICE_SET_HEV_CYCLE_STATE, {ATTR_POWER: True}, "no_hev", id="hev"
        ),
        pytest.param(SERVICE_EFFECT_PULSE, {}, "no_lifx_target", id="effect-action"),
    ],
)
async def test_lifx_actions_refused_by_components(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service: str,
    data: dict[str, Any],
    translation_key: str,
) -> None:
    """Test the LIFX actions a component cannot carry out are refused."""
    await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, DOMAIN, service, "uplight", **data)
    assert err.value.translation_key == translation_key


async def test_main_entity_writes_every_zone(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a main entity command covers the zones of both components."""
    device = await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, "brightness": 255},
        blocking=True,
    )

    _, colors = device.set_matrix_colors.await_args.args
    assert {color.brightness for color in colors} == {1.0}


RESTORED = [[30.0, 0.5, 0.9, 3500]]


async def _setup_with_restored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    colors: object,
    *,
    is_on: bool = False,
    stored: HSBK | None = None,
) -> CeilingLight:
    """Set up a Ceiling whose uplight restores the given colours."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id_for("uplight"), STATE_ON if is_on else STATE_OFF),
                {"colors": colors},
            )
        ],
    )
    device = create_reference_ceiling_light()
    device.state.uplight_is_on = is_on
    device.state.uplight_color = HSBK(30.0, 0.5, 0.9 if is_on else 0.0, 3500)
    device.state.stored_uplight_color = stored
    entry = await async_setup_lifx_entry(hass, device)
    await async_enable_components(hass, entry, entity_registry, device, CEILING_KEYS)
    return device


async def test_restored_colors_used_after_restart(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a bare turn on after a restart uses the remembered colour."""
    device = await _setup_with_restored(hass, entity_registry, RESTORED)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id_for("uplight")},
        blocking=True,
    )

    device.turn_uplight_on.assert_awaited_once_with(HSBK(30.0, 0.5, 0.9, 3500), 0.0)


@pytest.mark.parametrize(
    ("colors", "is_on", "stored"),
    [
        pytest.param(
            [[200.0, 0.5, 0.9, 3500]], False, None, id="hue-changed-elsewhere"
        ),
        pytest.param(None, False, None, id="nothing-remembered"),
        pytest.param(
            RESTORED, False, HSBK(45.0, 0.6, 0.7, 3500), id="library-memory-preferred"
        ),
        pytest.param([[30.0, 0.5, 0.0, 3500]], False, None, id="dark"),
    ],
)
async def test_restored_colors_ignored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    colors: list[list[float]] | None,
    is_on: bool,
    stored: HSBK | None,
) -> None:
    """Test restored colours that are stale, dark or shadowed are not used."""
    device = await _setup_with_restored(
        hass, entity_registry, colors, is_on=is_on, stored=stored
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id_for("uplight")},
        blocking=True,
    )

    device.turn_uplight_on.assert_awaited_once_with(None, 0.0)


async def test_restored_colors_used_only_once(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the restored colours are used only once."""
    device = await _setup_with_restored(hass, entity_registry, RESTORED)
    for _ in range(2):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id_for("uplight")},
            blocking=True,
        )

    assert device.turn_uplight_on.await_args_list[1].args == (None, 0.0)


async def test_dark_restored_colors_not_merged_onto(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a hue-only change does not merge onto dark restored colours."""
    device = await _setup_with_restored(hass, entity_registry, [[30.0, 0.5, 0.0, 3500]])

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, "uplight", hs_color=(120.0, 50.0))

    color, _ = device.turn_uplight_on.await_args.args
    assert color.hue == 120.0
    # The downlight's brightness is borrowed instead
    assert color.brightness == pytest.approx(0.5, abs=0.01)


@pytest.mark.parametrize(
    "colors",
    [
        pytest.param(5, id="not-a-list"),
        pytest.param([[30.0, 0.5, 0.9]], id="missing-kelvin"),
        pytest.param([["red", 0.5, 0.9, 3500]], id="not-a-number"),
        pytest.param([[400.0, 0.5, 0.9, 3500]], id="out-of-range"),
    ],
)
async def test_malformed_restored_colors_ignored(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, colors: object
) -> None:
    """Test saved colours that cannot be read are dropped rather than failing."""
    device = await _setup_with_restored(hass, entity_registry, colors)
    assert hass.states.get(entity_id_for("uplight")) is not None

    await _call(hass, LIGHT_DOMAIN, SERVICE_TURN_ON, "uplight")

    device.turn_uplight_on.assert_awaited_once_with(None, 0.0)


@pytest.mark.parametrize(
    ("restored", "stored", "expected"),
    [
        pytest.param(
            None,
            HSBK(60.0, 1.0, 0.4, 3500),
            [[60.0, 1.0, 0.4, 3500]],
            id="library-memory",
        ),
        pytest.param(RESTORED, None, RESTORED, id="restored-unused"),
        pytest.param(
            RESTORED, HSBK(60.0, 1.0, 0.0, 3500), RESTORED, id="library-memory-dark"
        ),
    ],
)
async def test_colors_saved_for_restart(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    restored: list[list[float]] | None,
    stored: HSBK | None,
    expected: list[list[float]],
) -> None:
    """Test the library's lit remembered colours are saved, else the restored ones."""
    device = await _setup_with_restored(hass, entity_registry, restored)
    device.state.stored_uplight_color = stored
    await async_trigger_update(hass)

    await async_mock_restore_state_shutdown_restart(hass)

    saved = next(
        entry
        for entry in hass_storage[RESTORE_STATE_KEY]["data"]
        if entry["state"]["entity_id"] == entity_id_for("uplight")
    )
    assert saved["extra_data"] == {"colors": expected}


@pytest.mark.parametrize(("factory", "keys"), COMPONENTS)
async def test_enabling_one_component_enables_the_other(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], Device],
    keys: tuple[str, ...],
) -> None:
    """Test enabling either component entity enables its partner."""
    await async_setup_lifx_entry(hass, factory())

    entity_registry.async_update_entity(entity_id_for(keys[0]), disabled_by=None)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id_for(keys[1])).disabled_by is None


async def test_disabling_one_component_disables_the_other(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test disabling either component entity disables its partner."""
    await _setup_components(
        hass, entity_registry, create_reference_mirror_light, MIRROR_KEYS
    )

    entity_registry.async_update_entity(
        entity_id_for("back"), disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entity_id_for("front")).disabled_by
        is er.RegistryEntryDisabler.USER
    )


async def test_rename_and_disable_together(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a rename in the same update as a disable still reaches the partner."""
    await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )

    entity_registry.async_update_entity(
        entity_id_for("uplight"),
        new_entity_id="light.renamed",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entity_id_for("downlight")).disabled_by
        is er.RegistryEntryDisabler.USER
    )


async def test_rename_alone_does_not_sync(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test renaming a component leaves its partner as it was."""
    await async_setup_lifx_entry(hass, create_reference_ceiling_light())

    entity_registry.async_update_entity(
        entity_id_for("uplight"), new_entity_id="light.renamed"
    )
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entity_id_for("downlight")).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


async def test_component_sync_stops_on_unload(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unloading the entry removes the registry listener."""
    entry = await async_setup_lifx_entry(hass, create_reference_ceiling_light())
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry.async_update_entity(entity_id_for("uplight"), disabled_by=None)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entity_id_for("downlight")).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


async def test_rename_then_later_disable_still_syncs(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a disable that arrives after an earlier, separate rename still syncs."""
    await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )
    entity_registry.async_update_entity(
        entity_id_for("uplight"), new_entity_id="light.renamed_uplight"
    )
    await hass.async_block_till_done()

    entity_registry.async_update_entity(
        "light.renamed_uplight", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entity_id_for("downlight")).disabled_by
        is er.RegistryEntryDisabler.USER
    )


async def test_disabling_the_main_light_disables_its_components(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test components cannot stay enabled once their main light is disabled."""
    await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )

    entity_registry.async_update_entity(
        MAIN_ENTITY_ID, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    for key in CEILING_KEYS:
        assert (
            entity_registry.async_get(entity_id_for(key)).disabled_by
            is er.RegistryEntryDisabler.USER
        )


async def test_enabling_a_component_enables_the_main_light(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test enabling a component brings back the main light it depends on."""
    await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )
    entity_registry.async_update_entity(
        MAIN_ENTITY_ID, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    entity_registry.async_update_entity(entity_id_for("uplight"), disabled_by=None)
    await hass.async_block_till_done()

    assert entity_registry.async_get(MAIN_ENTITY_ID).disabled_by is None
    assert entity_registry.async_get(entity_id_for("downlight")).disabled_by is None


@pytest.mark.parametrize(
    "platform",
    [
        pytest.param("other_integration", id="other-integration"),
        pytest.param(DOMAIN, id="other-lifx-device"),
    ],
)
async def test_unrelated_light_disable_does_not_touch_components(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, platform: str
) -> None:
    """Test disabling a light that is not this device's leaves its lights alone."""
    await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )
    other = entity_registry.async_get_or_create(
        Platform.LIGHT, platform, "d073d5000001"
    )

    entity_registry.async_update_entity(
        other.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(MAIN_ENTITY_ID).disabled_by is None
    for key in CEILING_KEYS:
        assert entity_registry.async_get(entity_id_for(key)).disabled_by is None


async def test_enabling_the_main_light_leaves_components_disabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test re-enabling the main light does not switch its components on too."""
    await _setup_components(
        hass, entity_registry, create_reference_ceiling_light, CEILING_KEYS
    )
    entity_registry.async_update_entity(
        MAIN_ENTITY_ID, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    entity_registry.async_update_entity(MAIN_ENTITY_ID, disabled_by=None)
    await hass.async_block_till_done()

    for key in CEILING_KEYS:
        assert (
            entity_registry.async_get(entity_id_for(key)).disabled_by
            is er.RegistryEntryDisabler.USER
        )
