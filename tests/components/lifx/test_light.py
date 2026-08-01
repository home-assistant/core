"""Tests for the LIFX light platform."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from lifx import (
    HSBK,
    Direction,
    EffectColorloop,
    EffectPulse,
    FirmwareEffect,
    LifxError,
    MultiZoneEffect,
    ThemeLibrary,
    TileEffectSkyType,
)
import pytest
import voluptuous as vol

from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.const import ATTR_DURATION, ATTR_POWER, ATTR_THEME
from homeassistant.components.lifx.light import (
    ATTR_INFRARED,
    ATTR_ZONES,
    LIFX_MIN_COLOR_RAMP,
)
from homeassistant.components.lifx.manager import (
    ATTR_CLOUD_SATURATION_MAX,
    ATTR_CLOUD_SATURATION_MIN,
    ATTR_CYCLES,
    ATTR_DIRECTION,
    ATTR_PALETTE,
    ATTR_PERIOD,
    ATTR_POWER_ON,
    ATTR_SATURATION_MAX,
    ATTR_SATURATION_MIN,
    ATTR_SKY_TYPE,
    ATTR_SPEED,
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
    SERVICE_PAINT_THEME,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_BRIGHTNESS_STEP,
    ATTR_BRIGHTNESS_STEP_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_ENTITY_ID,
    ATTR_MODE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util

from . import (
    SERIAL,
    async_setup_lifx_entries,
    async_setup_lifx_entry,
    async_trigger_update,
)
from .helpers import (
    MockDevice,
    assert_color_written,
    create_mock_ceiling_light,
    create_mock_hev_light,
    create_mock_infrared_light,
    create_mock_light,
    create_mock_matrix_light,
    create_mock_multizone_light,
    create_reference_matrix_light,
)

from tests.common import async_fire_time_changed

ENTITY_ID = "light.my_group_my_bulb"
OTHER_IP_ADDRESS = "127.0.0.2"
OTHER_SERIAL = "d073d5aabbcc"
OTHER_MAC_ADDRESS = "d0:73:d5:aa:bb:cc"
OTHER_LABEL = "Other Bulb"
OTHER_ENTITY_ID = "light.my_group_other_bulb"

pytestmark = pytest.mark.usefixtures("mock_effect_conductor")


@pytest.fixture(autouse=True)
def patch_lifx_state_settle_delay() -> Any:
    """Set the state settle delay to zero."""
    with (
        patch("homeassistant.components.lifx.light.LIFX_STATE_SETTLE_DELAY", 0),
        patch(
            "homeassistant.components.lifx.discovery.async_discover_devices",
            AsyncMock(return_value={}),
        ),
    ):
        yield


async def test_light_identity_is_unchanged(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity and device identity from public device state."""
    device = create_mock_light()
    entry = await async_setup_lifx_entry(hass, device)

    assert entity_registry.async_get(ENTITY_ID).unique_id == SERIAL
    registry_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, SERIAL), entry.entry_id
    )
    assert registry_device.identifiers == {(DOMAIN, SERIAL)}


async def test_color_light_state_and_modes(hass: HomeAssistant) -> None:
    """Test public color state renders with unchanged Home Assistant modes."""
    device = create_mock_light()
    device.state.power = 65535
    device.state.color = HSBK(20.0, 0.25, 0.75, 4000)
    await async_setup_lifx_entry(hass, device)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 191
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
    assert state.attributes[ATTR_HS_COLOR] == (20.0, 25.0)
    assert state.attributes[ATTR_EFFECT] is None


@pytest.mark.parametrize(
    ("kelvin_range", "expected_mode"),
    [
        pytest.param((2500, 9000), ColorMode.COLOR_TEMP, id="color_temp"),
        pytest.param((2700, 2700), ColorMode.BRIGHTNESS, id="brightness"),
    ],
)
async def test_white_light_modes(
    hass: HomeAssistant,
    kelvin_range: tuple[int, int],
    expected_mode: ColorMode,
) -> None:
    """Test white and brightness-only capability presentation."""
    device = create_mock_light()
    capabilities = device.state.capabilities
    capabilities.has_color = False
    capabilities.kelvin_min, capabilities.kelvin_max = kelvin_range
    device.state.power = 65535
    device.state.color = HSBK(0.0, 0.0, 0.5, 4000)
    await async_setup_lifx_entry(hass, device)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_COLOR_MODE] == expected_mode
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [expected_mode]
    assert state.attributes[ATTR_EFFECT_LIST] == [
        SERVICE_EFFECT_PULSE,
        SERVICE_EFFECT_STOP,
    ]


@pytest.mark.parametrize(
    ("factory", "effect_list"),
    [
        (
            create_mock_multizone_light,
            [
                SERVICE_EFFECT_COLORLOOP,
                SERVICE_EFFECT_PULSE,
                SERVICE_EFFECT_MOVE,
                SERVICE_EFFECT_STOP,
            ],
        ),
        (
            create_mock_matrix_light,
            [
                SERVICE_EFFECT_COLORLOOP,
                SERVICE_EFFECT_FLAME,
                SERVICE_EFFECT_PULSE,
                SERVICE_EFFECT_MORPH,
                SERVICE_EFFECT_STOP,
            ],
        ),
        (
            create_mock_ceiling_light,
            [
                SERVICE_EFFECT_COLORLOOP,
                SERVICE_EFFECT_FLAME,
                SERVICE_EFFECT_PULSE,
                SERVICE_EFFECT_MORPH,
                SERVICE_EFFECT_SKY,
                SERVICE_EFFECT_STOP,
            ],
        ),
    ],
)
async def test_zoned_effect_names_and_firmware_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    factory: Callable[[], MockDevice],
    effect_list: list[str],
) -> None:
    """Test existing zoned effect names without exposing ceiling subentities."""
    device = factory()
    device.state.power = 65535
    device.state.effect = FirmwareEffect.MOVE
    await async_setup_lifx_entry(hass, device)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_EFFECT_LIST] == effect_list
    assert state.attributes[ATTR_EFFECT] == "effect_move"
    assert [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == DOMAIN and entry.domain == LIGHT_DOMAIN
    ] == [entity_registry.async_get(ENTITY_ID)]


@pytest.mark.parametrize(
    ("running_effect", "expected_effect"),
    [
        pytest.param(EffectPulse(), "effect_pulse", id="pulse"),
        pytest.param(EffectColorloop(), "effect_colorloop", id="colorloop"),
        pytest.param(None, None, id="idle"),
    ],
)
async def test_running_software_effect_is_reported(
    hass: HomeAssistant,
    mock_effect_conductor: MagicMock,
    running_effect: EffectPulse | EffectColorloop | None,
    expected_effect: str | None,
) -> None:
    """Test a running software effect is reported by the light entity."""
    device = create_mock_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)
    mock_effect_conductor.effect.return_value = running_effect

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_EFFECT] == expected_effect


async def test_effect_pulse_uses_public_effect(
    hass: HomeAssistant, mock_effect_conductor: MagicMock
) -> None:
    """Test pulse service constructs a public-unit effect."""
    device = create_mock_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_PULSE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_POWER_ON: False,
            ATTR_MODE: "breathe",
            ATTR_PERIOD: 2.5,
            ATTR_CYCLES: 4,
            ATTR_HS_COLOR: (120.0, 50.0),
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )

    effect, participants = mock_effect_conductor.start.await_args.args
    assert isinstance(effect, EffectPulse)
    assert effect.power_on is False
    assert effect.mode == "breathe"
    assert effect.period == 2.5
    assert effect.cycles == 4
    assert effect.color == HSBK(120.0, 0.5, 128 / 255, 3500)
    assert participants == [device]


async def test_effect_colorloop_uses_public_effect_defaults(
    hass: HomeAssistant, mock_effect_conductor: MagicMock
) -> None:
    """Test colorloop service constructs a normalized public effect."""
    device = create_mock_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_COLORLOOP,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_BRIGHTNESS_PCT: 50,
            ATTR_SATURATION_MIN: 90,
        },
        blocking=True,
    )

    effect, participants = mock_effect_conductor.start.await_args.args
    assert isinstance(effect, EffectColorloop)
    assert effect.power_on is True
    assert effect.period == 60.0
    assert effect.change == 20.0
    assert effect.spread == 30.0
    assert effect.brightness == 0.5
    assert effect.saturation_min == 0.9
    assert effect.saturation_max == 1.0
    assert effect.transition is None
    assert participants == [device]


async def test_effect_colorloop_orders_saturation_bounds(
    hass: HomeAssistant, mock_effect_conductor: MagicMock
) -> None:
    """Test a saturation_max below the default minimum is still accepted."""
    await async_setup_lifx_entry(hass, create_mock_light())

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_COLORLOOP,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SATURATION_MAX: 50},
        blocking=True,
    )

    effect = mock_effect_conductor.start.await_args.args[0]
    assert effect.saturation_min == 0.5
    assert effect.saturation_max == 0.8


async def test_effect_colorloop_accepts_absolute_brightness(
    hass: HomeAssistant, mock_effect_conductor: MagicMock
) -> None:
    """Test colorloop normalises the 0-255 brightness attribute."""
    await async_setup_lifx_entry(hass, create_mock_light())

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_COLORLOOP,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    effect = mock_effect_conductor.start.await_args.args[0]
    assert effect.brightness == 128 / 255


async def test_software_effect_errors_become_home_assistant_errors(
    hass: HomeAssistant, mock_effect_conductor: MagicMock
) -> None:
    """Test conductor failures surface as Home Assistant errors."""
    await async_setup_lifx_entry(hass, create_mock_light())
    mock_effect_conductor.start.side_effect = LifxError("software boom")

    with pytest.raises(HomeAssistantError, match="software boom"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EFFECT_PULSE,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def test_stopping_an_effect_to_set_state_can_fail(
    hass: HomeAssistant, mock_effect_conductor: MagicMock
) -> None:
    """Test the pre-effect state restore that precedes every command is reported."""
    await async_setup_lifx_entry(hass, create_mock_light())
    mock_effect_conductor.stop.side_effect = LifxError("restore boom")

    with pytest.raises(HomeAssistantError, match="restore boom"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "service_data", "effect_type", "expected_kwargs"),
    [
        pytest.param(
            SERVICE_EFFECT_FLAME,
            {ATTR_SPEED: 4},
            FirmwareEffect.FLAME,
            {"speed": 4},
            id="flame",
        ),
        pytest.param(
            SERVICE_EFFECT_MORPH,
            {ATTR_SPEED: 6, ATTR_THEME: "autumn"},
            FirmwareEffect.MORPH,
            {"speed": 6, "palette": ThemeLibrary.get("autumn").colors},
            id="morph",
        ),
    ],
)
async def test_matrix_effects_use_public_firmware_api(
    hass: HomeAssistant,
    service: str,
    service_data: dict[str, Any],
    effect_type: FirmwareEffect,
    expected_kwargs: dict[str, Any],
) -> None:
    """Test matrix effects delegate public firmware operations."""
    device = create_mock_matrix_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    device.set_power.assert_awaited_once_with(True, duration=0.0)
    device.set_effect.assert_awaited_once_with(effect_type, **expected_kwargs)


async def test_firmware_effect_errors_become_home_assistant_errors(
    hass: HomeAssistant,
) -> None:
    """Test firmware effect failures surface as Home Assistant errors."""
    device = create_mock_matrix_light()
    device.state.power = 65535
    device.set_effect.side_effect = LifxError("firmware boom")
    await async_setup_lifx_entry(hass, device)

    with pytest.raises(HomeAssistantError, match="firmware boom"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EFFECT_FLAME,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def test_effect_theme_schema_offers_every_library_theme(
    hass: HomeAssistant,
) -> None:
    """Test effect services accept the themes the library currently ships."""
    device = create_mock_matrix_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_MORPH,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_THEME: "arctic"},
        blocking=True,
    )

    device.set_effect.assert_awaited_once()
    assert (
        device.set_effect.await_args.kwargs["palette"]
        == ThemeLibrary.get("arctic").colors
    )


async def test_sky_effect_uses_public_firmware_api(hass: HomeAssistant) -> None:
    """Test sky service delegates public enum and palette values."""
    device = create_mock_ceiling_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_SKY,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_SPEED: 50,
            ATTR_SKY_TYPE: "Clouds",
            ATTR_CLOUD_SATURATION_MIN: 50,
            ATTR_CLOUD_SATURATION_MAX: 180,
            ATTR_PALETTE: [(200, 100, 1, 3500), (40, 50, 100, 3500)],
        },
        blocking=True,
    )

    device.set_effect.assert_awaited_once_with(
        FirmwareEffect.SKY,
        speed=50,
        palette=[HSBK(200, 1.0, 0.01, 3500), HSBK(40, 0.5, 1.0, 3500)],
        sky_type=TileEffectSkyType.CLOUDS,
        cloud_saturation_min=50,
        cloud_saturation_max=180,
    )


async def test_sky_effect_without_a_palette_omits_it(
    hass: HomeAssistant,
) -> None:
    """Test omitting the palette sends no palette and skips the power on."""
    device = create_mock_ceiling_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_SKY,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POWER_ON: False},
        blocking=True,
    )

    # The library rejects an empty palette, so it is not given one at all
    assert device.set_effect.await_args.kwargs["palette"] is None
    device.set_power.assert_not_awaited()


async def test_move_effect_uses_public_firmware_api(hass: HomeAssistant) -> None:
    """Test move service delegates theme and firmware operations."""
    device = create_mock_multizone_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_MOVE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_SPEED: 4.5,
            ATTR_DIRECTION: "left",
            ATTR_THEME: "sports",
        },
        blocking=True,
    )

    device.apply_theme.assert_awaited_once()
    theme = device.apply_theme.await_args.args[0]
    assert theme.colors == ThemeLibrary.get("sports").colors
    assert device.apply_theme.await_args.kwargs == {"power_on": False, "duration": 4}
    expected = MultiZoneEffect(
        FirmwareEffect.MOVE,
        4500,
        parameters=[0, int(Direction.FORWARD), 0, 0, 0, 0, 0, 0],
    )
    device.set_effect.assert_awaited_once_with(expected)


@pytest.mark.parametrize(
    ("factory", "method", "args"),
    [
        pytest.param(
            create_mock_matrix_light,
            "set_effect",
            (FirmwareEffect.OFF,),
            id="matrix",
        ),
        pytest.param(create_mock_multizone_light, "stop_effect", (), id="multizone"),
    ],
)
async def test_effect_stop_uses_compatible_public_firmware_api(
    hass: HomeAssistant,
    mock_effect_conductor: MagicMock,
    factory: Callable[[], MockDevice],
    method: str,
    args: tuple[object, ...],
) -> None:
    """Test stop service delegates only the compatible firmware operation."""
    device = factory()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_STOP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_effect_conductor.stop.assert_awaited_once_with([device])
    getattr(device, method).assert_awaited_once_with(*args)


@pytest.mark.parametrize(
    ("service_data", "expected_colors"),
    [
        pytest.param(
            {ATTR_THEME: "autumn"}, ThemeLibrary.get("autumn").colors, id="library"
        ),
        pytest.param(
            {ATTR_PALETTE: [(0, 100, 100, 3500), (240, 50, 25, 6500)]},
            [HSBK(0, 1.0, 1.0, 3500), HSBK(240, 0.5, 0.25, 6500)],
            id="palette",
        ),
    ],
)
async def test_paint_theme_uses_public_device_api(
    hass: HomeAssistant,
    service_data: dict[str, Any],
    expected_colors: list[HSBK],
) -> None:
    """Test paint service applies one public theme to each target."""
    device = create_mock_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PAINT_THEME,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_POWER_ON: False,
            ATTR_TRANSITION: 4,
            **service_data,
        },
        blocking=True,
    )

    device.apply_theme.assert_awaited_once()
    theme = device.apply_theme.await_args.args[0]
    assert theme.colors == expected_colors
    assert device.apply_theme.await_args.kwargs == {"power_on": False, "duration": 4}


async def test_typed_light_sets_public_hsbk(hass: HomeAssistant) -> None:
    """Test Home Assistant color values are sent in public library units."""
    device = create_mock_light()
    device.state.power = 65535
    device.state.color = HSBK(20.0, 0.25, 0.75, 4000)
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HS_COLOR: (120.0, 50.0),
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )

    # A color request resets the light to neutral white
    assert_color_written(device, HSBK(120.0, 0.5, 128 / 255, 3500))
    device.set_color.assert_not_awaited()


@pytest.mark.parametrize(
    ("service_data", "expected", "written"),
    [
        pytest.param(
            {ATTR_COLOR_TEMP_KELVIN: 2700},
            HSBK(20.0, 0.0, 0.75, 2700),
            {"hue": False, "brightness": False},
            id="color_temp",
        ),
        pytest.param(
            {ATTR_BRIGHTNESS_PCT: 50},
            HSBK(20.0, 0.25, 0.5, 4000),
            {"hue": False, "saturation": False, "kelvin": False},
            id="brightness_pct",
        ),
        pytest.param(
            {ATTR_COLOR_NAME: "red"},
            HSBK(0.0, 1.0, 0.75, 3500),
            {"brightness": False},
            id="color_name",
        ),
        pytest.param(
            {ATTR_RGB_COLOR: (255, 0, 0)},
            HSBK(0.0, 1.0, 0.75, 3500),
            {"brightness": False},
            id="rgb_color",
        ),
        pytest.param(
            {ATTR_XY_COLOR: (0.3, 0.6)},
            HSBK(91.915, 0.73725, 0.75, 3500),
            {"brightness": False},
            id="xy_color",
        ),
    ],
)
async def test_public_color_inputs(
    hass: HomeAssistant,
    service_data: dict[str, Any],
    expected: HSBK,
    written: dict[str, bool],
) -> None:
    """Test retained color input forms use public HSBK units."""
    device = create_mock_light()
    device.state.power = 65535
    device.state.color = HSBK(20.0, 0.25, 0.75, 4000)
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    assert_color_written(device, expected, **written)


async def test_kelvin_outside_the_protocol_range_is_rejected(
    hass: HomeAssistant,
) -> None:
    """Test a kelvin the protocol cannot carry surfaces as a Home Assistant error."""
    device = create_mock_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)

    with pytest.raises(ServiceValidationError, match="not valid"):
        await hass.services.async_call(
            DOMAIN,
            "set_state",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COLOR_TEMP_KELVIN: 1200},
            blocking=True,
        )

    device.set_waveform_optional.assert_not_awaited()


async def test_unknown_color_name_falls_back_to_neutral_white(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an unrecognised color name warns and leaves the light white."""
    device = create_mock_light()
    device.state.power = 65535
    device.state.color = HSBK(20.0, 0.25, 0.75, 4000)
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COLOR_NAME: "burnt sienna"},
        blocking=True,
    )

    assert "Got unknown color burnt sienna" in caplog.text
    assert_color_written(device, HSBK(0.0, 0.0, 0.75, 3500), brightness=False)


@pytest.mark.parametrize(
    ("step", "expected_brightness"),
    [
        ({ATTR_BRIGHTNESS_STEP: 64}, 192 / 255),
        ({ATTR_BRIGHTNESS_STEP_PCT: 25}, 191 / 255),
    ],
)
async def test_brightness_steps(
    hass: HomeAssistant,
    step: dict[str, Any],
    expected_brightness: float,
) -> None:
    """Test retained brightness-step automation behavior."""
    device = create_mock_light()
    device.state.power = 65535
    device.state.color = HSBK(0.0, 0.0, 0.5, 4000)
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: ENTITY_ID, **step},
        blocking=True,
    )

    assert_color_written(
        device,
        HSBK(0.0, 0.0, expected_brightness, 4000),
        hue=False,
        saturation=False,
        kelvin=False,
    )


@pytest.mark.parametrize(
    ("initial_power", "service", "data", "expected"),
    [
        (65535, SERVICE_TURN_OFF, {ATTR_TRANSITION: 5}, (False, 5.0)),
        (0, SERVICE_TURN_OFF, {ATTR_TRANSITION: 5}, (False, 0.0)),
        (0, SERVICE_TURN_ON, {ATTR_TRANSITION: 5}, (True, 5.0)),
    ],
)
async def test_power_transitions_use_seconds(
    hass: HomeAssistant,
    initial_power: int,
    service: str,
    data: dict[str, Any],
    expected: tuple[bool, float],
) -> None:
    """Test power transitions preserve existing on/off semantics in seconds."""
    device = create_mock_light()
    device.state.power = initial_power
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )

    device.set_power.assert_awaited_once_with(expected[0], duration=expected[1])


async def test_color_is_set_before_fading_on(hass: HomeAssistant) -> None:
    """Test an off light receives color immediately before a power fade."""
    device = create_mock_light()
    device.state.power = 0
    device.state.color = HSBK(20.0, 0.25, 0.75, 4000)
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HS_COLOR: (120.0, 50.0),
            ATTR_TRANSITION: 5,
        },
        blocking=True,
    )

    # The power fade ramps the color into place, so it is written instantly
    assert_color_written(
        device, HSBK(120.0, 0.5, 0.75, 3500), period=0.0, brightness=False
    )
    device.set_power.assert_awaited_once_with(True, duration=5.0)


async def test_transition_requests_one_postponed_refresh(
    hass: HomeAssistant,
) -> None:
    """Test a transition refreshes immediately and once when it finishes."""
    device = create_mock_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)
    device.refresh_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TRANSITION: 5},
        blocking=True,
    )
    device.refresh_state.assert_awaited_once()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert device.refresh_state.await_count == 2


async def test_superseding_transition_cancels_old_refresh(
    hass: HomeAssistant,
) -> None:
    """Test a new operation cancels the previous transition-end refresh."""
    device = create_mock_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)
    device.refresh_state.reset_mock()

    first_cancel = MagicMock()
    second_cancel = MagicMock()
    with patch(
        "homeassistant.components.lifx.light.async_call_later",
        side_effect=[first_cancel, second_cancel],
    ):
        for brightness in (100, 200):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: ENTITY_ID,
                    ATTR_BRIGHTNESS: brightness,
                    ATTR_TRANSITION: 5,
                },
                blocking=True,
            )

    first_cancel.assert_called_once_with()
    second_cancel.assert_not_called()


@pytest.mark.parametrize("extended", [True, False], ids=["extended", "legacy"])
async def test_multizone_selection(hass: HomeAssistant, extended: bool) -> None:
    """Test selected zones send the full span whatever the wire protocol is."""
    device = create_mock_multizone_light(extended=extended)
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ZONES: [0],
            ATTR_BRIGHTNESS: 128,
            ATTR_TRANSITION: 2,
        },
        blocking=True,
    )

    device.set_all_color_zones.assert_awaited_once_with(
        [HSBK(300.0, 1.0, 128 / 255, 3500), HSBK(255.0, 1.0, 1.0, 3500)],
        start=0,
        end=0,
        duration=2.0,
    )


async def test_multizone_brightness_preserves_zone_colors(
    hass: HomeAssistant,
) -> None:
    """Test whole-strip brightness retains each public zone color."""
    device = create_mock_multizone_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    device.set_all_color_zones.assert_awaited_once_with(
        [
            HSBK(300.0, 1.0, 128 / 255, 3500),
            HSBK(255.0, 1.0, 128 / 255, 3500),
        ],
        start=0,
        end=1,
        duration=LIFX_MIN_COLOR_RAMP,
    )
    device.set_waveform_optional.assert_not_awaited()


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        pytest.param(
            {ATTR_HS_COLOR: (120.0, 50.0), ATTR_BRIGHTNESS: 128},
            HSBK(120.0, 0.5, 128 / 255, 3500),
            id="color_and_brightness",
        ),
        pytest.param(
            {ATTR_COLOR_TEMP_KELVIN: 2700, ATTR_BRIGHTNESS: 128},
            HSBK(0.0, 0.0, 128 / 255, 2700),
            id="color_temp_and_brightness",
        ),
    ],
)
async def test_multizone_full_overwrite_skips_reading_the_strip(
    hass: HomeAssistant, service_data: dict[str, Any], expected: HSBK
) -> None:
    """Test a change that leaves nothing of a zone showing writes without a read."""
    device = create_mock_multizone_light()
    device.state.power = 65535
    device.state.zones = [HSBK(300.0, 1.0, 1.0, 3500), HSBK(255.0, 1.0, 0.25, 3500)]
    await async_setup_lifx_entry(hass, device)
    device.refresh_state.reset_mock()

    reads_before_write = None

    async def _record_reads(*args: Any, **kwargs: Any) -> None:
        nonlocal reads_before_write
        reads_before_write = device.refresh_state.await_count

    device.set_all_color_zones.side_effect = _record_reads

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    device.set_all_color_zones.assert_awaited_once_with(
        [expected, expected],
        start=0,
        end=1,
        duration=LIFX_MIN_COLOR_RAMP,
    )
    assert reads_before_write == 0


async def test_multizone_selection_writes_only_the_requested_window(
    hass: HomeAssistant,
) -> None:
    """Test a non-zero zone selection leaves the zones outside it untouched."""
    device = create_mock_multizone_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ZONES: [1], ATTR_HS_COLOR: (120.0, 50.0)},
        blocking=True,
    )

    device.set_all_color_zones.assert_awaited_once_with(
        [HSBK(300.0, 1.0, 1.0, 3500), HSBK(120.0, 0.5, 1.0, 3500)],
        start=1,
        end=1,
        duration=LIFX_MIN_COLOR_RAMP,
    )


async def test_multizone_selection_outside_the_strip_writes_nothing(
    hass: HomeAssistant,
) -> None:
    """Test zone numbers past the end of the strip are dropped."""
    device = create_mock_multizone_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ZONES: [99], ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    device.set_all_color_zones.assert_not_awaited()
    device.set_waveform_optional.assert_not_awaited()


@pytest.mark.parametrize(
    ("service_data", "reads_expected"),
    [
        pytest.param({ATTR_HS_COLOR: (120.0, 50.0)}, 1, id="partial_change_reads"),
        pytest.param(
            {ATTR_HS_COLOR: (120.0, 50.0), ATTR_BRIGHTNESS: 128},
            0,
            id="full_overwrite_skips_read",
        ),
    ],
)
async def test_matrix_reads_the_tiles_before_merging_over_them(
    hass: HomeAssistant, service_data: dict[str, Any], reads_expected: int
) -> None:
    """Test tiles are only merged over after the device has been read."""
    device = create_mock_matrix_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)
    device.refresh_state.reset_mock()

    reads_before_write = None

    async def _record_reads(*args: Any, **kwargs: Any) -> None:
        nonlocal reads_before_write
        reads_before_write = device.refresh_state.await_count

    device.set_matrix_colors.side_effect = _record_reads

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    assert reads_before_write == reads_expected


async def test_matrix_without_tile_colors_sets_the_whole_device(
    hass: HomeAssistant,
) -> None:
    """Test a matrix device with no cached tile colors writes the device color."""
    device = create_mock_matrix_light()
    device.state.power = 65535
    device.state.tile_colors = []
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HS_COLOR: (120.0, 50.0)},
        blocking=True,
    )

    assert_color_written(device, HSBK(120.0, 0.5, 1.0, 3500), brightness=False)
    device.set_matrix_colors.assert_not_awaited()


async def test_turn_on_with_effect_delegates_to_the_effect_service(
    hass: HomeAssistant, mock_effect_conductor: MagicMock
) -> None:
    """Test the effect attribute of light.turn_on calls the LIFX effect service."""
    device = create_mock_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_EFFECT: SERVICE_EFFECT_PULSE},
        blocking=True,
    )
    # The effect service is called without waiting for it to finish
    await hass.async_block_till_done()

    effect, participants = mock_effect_conductor.start.await_args.args
    assert isinstance(effect, EffectPulse)
    assert participants == [device]
    device.set_waveform_optional.assert_not_awaited()


async def test_multizone_color_preserves_zone_brightness(hass: HomeAssistant) -> None:
    """Test a whole-strip color change keeps each zone at its own brightness."""
    device = create_mock_multizone_light()
    device.state.power = 65535
    device.state.zones = [HSBK(300.0, 1.0, 1.0, 3500), HSBK(255.0, 1.0, 0.25, 3500)]
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HS_COLOR: (120.0, 50.0)},
        blocking=True,
    )

    device.set_all_color_zones.assert_awaited_once_with(
        [HSBK(120.0, 0.5, 1.0, 3500), HSBK(120.0, 0.5, 0.25, 3500)],
        start=0,
        end=1,
        duration=LIFX_MIN_COLOR_RAMP,
    )
    device.set_waveform_optional.assert_not_awaited()


async def test_multizone_color_keeps_the_brightness_of_a_dark_strip(
    hass: HomeAssistant,
) -> None:
    """Test a color-only change on a dark strip reads its zones where they are."""
    device = create_mock_multizone_light()
    device.state.zones = [HSBK(300.0, 1.0, 1.0, 3500), HSBK(255.0, 1.0, 0.25, 3500)]
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HS_COLOR: (120.0, 50.0)},
        blocking=True,
    )

    # Powered on once for the caller, since a dark strip still reports its zones
    assert device.set_power.await_args_list == [call(True, duration=0.0)]
    device.set_all_color_zones.assert_awaited_once_with(
        [HSBK(120.0, 0.5, 1.0, 3500), HSBK(120.0, 0.5, 0.25, 3500)],
        start=0,
        end=1,
        duration=0.0,
    )


@pytest.mark.parametrize(
    "factory", [create_mock_matrix_light, create_mock_ceiling_light]
)
async def test_matrix_color_uses_public_convenience_api(
    hass: HomeAssistant, factory: Callable[[], MockDevice]
) -> None:
    """Test matrix and ceiling color changes delegate tile mechanics."""
    device = factory()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HS_COLOR: (120.0, 50.0),
            ATTR_TRANSITION: 1.5,
        },
        blocking=True,
    )

    expected = HSBK(120.0, 0.5, 1.0, 3500)
    device.set_matrix_colors.assert_awaited_once_with(0, [expected] * 64, duration=1500)


@pytest.mark.parametrize(
    "factory", [create_mock_matrix_light, create_mock_ceiling_light]
)
async def test_matrix_color_preserves_tile_brightness(
    hass: HomeAssistant, factory: Callable[[], MockDevice]
) -> None:
    """Test a whole-device color change keeps each tile at its own brightness."""
    device = factory()
    device.state.power = 65535
    device.state.tile_colors = [HSBK(0.0, 0.0, 1.0, 3500)] * 32 + [
        HSBK(0.0, 0.0, 0.25, 3500)
    ] * 32
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HS_COLOR: (120.0, 50.0)},
        blocking=True,
    )

    device.set_matrix_colors.assert_awaited_once_with(
        0,
        [HSBK(120.0, 0.5, 1.0, 3500)] * 32 + [HSBK(120.0, 0.5, 0.25, 3500)] * 32,
        duration=round(LIFX_MIN_COLOR_RAMP * 1000),
    )


async def test_matrix_color_writes_each_tile_in_the_chain(
    hass: HomeAssistant,
) -> None:
    """Test a chained matrix device is written one tile at a time."""
    device = create_reference_matrix_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HS_COLOR: (120.0, 50.0)},
        blocking=True,
    )

    expected = [HSBK(120.0, 0.5, 0.5, 3500)] * 64
    assert device.set_matrix_colors.await_args_list == [
        call(tile_index, expected, duration=round(LIFX_MIN_COLOR_RAMP * 1000))
        for tile_index in range(5)
    ]


async def test_matrix_color_stops_at_a_short_color_list(hass: HomeAssistant) -> None:
    """Test a chain reporting fewer colors than zones writes only whole tiles."""
    device = create_reference_matrix_light()
    device.state.tile_colors = device.state.tile_colors[:100]
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HS_COLOR: (120.0, 50.0)},
        blocking=True,
    )

    device.set_matrix_colors.assert_awaited_once_with(
        0,
        [HSBK(120.0, 0.5, 0.5, 3500)] * 64,
        duration=round(LIFX_MIN_COLOR_RAMP * 1000),
    )


@pytest.mark.parametrize(
    "factory", [create_mock_matrix_light, create_mock_ceiling_light]
)
async def test_matrix_brightness_preserves_tile_colors(
    hass: HomeAssistant, factory: Callable[[], MockDevice]
) -> None:
    """Test matrix brightness retains each public tile color."""
    device = factory()
    device.state.power = 65535
    device.state.chain[0].width = 2
    device.state.chain[0].height = 1
    device.state.tile_colors = [
        HSBK(10.0, 0.2, 0.3, 2700),
        HSBK(220.0, 0.8, 0.9, 6500),
    ]
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_BRIGHTNESS: 128,
            ATTR_TRANSITION: 1.5,
        },
        blocking=True,
    )

    device.set_matrix_colors.assert_awaited_once_with(
        0,
        [
            HSBK(10.0, 0.2, 128 / 255, 2700),
            HSBK(220.0, 0.8, 128 / 255, 6500),
        ],
        duration=1500,
    )


async def test_deprecated_infrared_uses_public_level(hass: HomeAssistant) -> None:
    """Test the deprecated infrared field delegates a normalized public level."""
    device = create_mock_infrared_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INFRARED: 100},
        blocking=True,
    )

    device.set_infrared.assert_awaited_once_with(100 / 255)


async def test_hev_cycle_service(hass: HomeAssistant) -> None:
    """Test HEV cycle control retains the existing entity service."""
    device = create_mock_hev_light()
    await async_setup_lifx_entry(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_hev_cycle_state",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POWER: True, ATTR_DURATION: 12},
        blocking=True,
    )

    device.set_hev_cycle.assert_awaited_once_with(True, 12)


async def test_hev_cycle_library_error_becomes_home_assistant_error(
    hass: HomeAssistant,
) -> None:
    """Test a library failure surfaces as a Home Assistant error."""
    device = create_mock_hev_light()
    await async_setup_lifx_entry(hass, device)
    device.set_hev_cycle.side_effect = LifxError("device unreachable")

    with pytest.raises(HomeAssistantError, match="device unreachable"):
        await hass.services.async_call(
            DOMAIN,
            "set_hev_cycle_state",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POWER: True},
            blocking=True,
        )


async def test_hev_cycle_rejected_for_regular_light(hass: HomeAssistant) -> None:
    """Test the action a LIFX Clean bulb registers is turned down by other lights."""
    regular = create_mock_light(
        ip=OTHER_IP_ADDRESS, serial=OTHER_SERIAL, mac_address=OTHER_MAC_ADDRESS
    )
    regular.state.label = OTHER_LABEL
    await async_setup_lifx_entries(hass, [create_mock_hev_light(), regular])

    with pytest.raises(ServiceValidationError, match="does not have HEV LEDs"):
        await hass.services.async_call(
            DOMAIN,
            "set_hev_cycle_state",
            {ATTR_ENTITY_ID: OTHER_ENTITY_ID, ATTR_POWER: True},
            blocking=True,
        )


async def test_hev_cycle_action_is_not_offered_without_a_clean_bulb(
    hass: HomeAssistant,
) -> None:
    """Test a setup without HEV LEDs anywhere does not register the action."""
    await async_setup_lifx_entry(hass, create_mock_light())

    assert hass.states.get(ENTITY_ID) is not None
    assert not hass.services.has_service(DOMAIN, "set_hev_cycle_state")


async def test_infrared_rejected_for_light_without_infrared(
    hass: HomeAssistant,
) -> None:
    """Test the deprecated infrared attribute rejects an unsupported device."""
    await async_setup_lifx_entry(hass, create_mock_light())

    with pytest.raises(ServiceValidationError, match="does not have infrared LEDs"):
        await hass.services.async_call(
            DOMAIN,
            "set_state",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INFRARED: 128},
            blocking=True,
        )


async def test_effect_without_a_lifx_target_is_rejected(hass: HomeAssistant) -> None:
    """Test an effect action that resolves to no LIFX light reports it."""
    await async_setup_lifx_entry(hass, create_mock_light())

    with pytest.raises(ServiceValidationError, match="include no LIFX light"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EFFECT_PULSE,
            {ATTR_ENTITY_ID: "light.does_not_exist"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "message"),
    [
        pytest.param(
            SERVICE_EFFECT_FLAME, "no LIFX matrix light", id="flame-needs-matrix"
        ),
        pytest.param(
            SERVICE_EFFECT_MORPH, "no LIFX matrix light", id="morph-needs-matrix"
        ),
        pytest.param(SERVICE_EFFECT_SKY, "no LIFX matrix light", id="sky-needs-matrix"),
        pytest.param(
            SERVICE_EFFECT_MOVE, "no LIFX multizone light", id="move-needs-multizone"
        ),
    ],
)
async def test_firmware_effect_named_on_an_incapable_light_is_rejected(
    hass: HomeAssistant, service: str, message: str
) -> None:
    """Test a firmware effect reports a target set that cannot run it."""
    device = create_mock_light()
    await async_setup_lifx_entry(hass, device)

    with pytest.raises(ServiceValidationError, match=message):
        await hass.services.async_call(
            DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    device.set_power.assert_not_called()


async def test_firmware_effect_on_an_area_without_a_capable_light_is_a_no_op(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an area that holds a LIFX light but no matrix one is not an error.

    Naming a light that cannot run the effect is a mistake, but sweeping an
    area that happens to hold none is not.
    """
    device = create_mock_light()
    entry = await async_setup_lifx_entry(hass, device)
    area = area_registry.async_create("No Matrix Here")
    registered = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert registered is not None
    device_registry.async_update_device(registered.id, area_id=area.id)

    await hass.services.async_call(
        DOMAIN, SERVICE_EFFECT_FLAME, {ATTR_AREA_ID: area.id}, blocking=True
    )

    device.set_power.assert_not_called()


async def test_effect_on_an_area_without_a_lifx_light_is_a_no_op(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test an effect action on an area holding no LIFX light does nothing."""
    device = create_mock_light()
    await async_setup_lifx_entry(hass, device)
    area = area_registry.async_create("No LIFX Here")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_PULSE,
        {ATTR_AREA_ID: area.id},
        blocking=True,
    )

    device.set_waveform_optional.assert_not_called()


@pytest.mark.parametrize(
    ("factory", "method", "domain", "service", "data"),
    [
        (
            create_mock_light,
            "set_waveform_optional",
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_HS_COLOR: (120.0, 50.0)},
        ),
        (create_mock_light, "set_power", LIGHT_DOMAIN, SERVICE_TURN_OFF, {}),
        (
            create_mock_multizone_light,
            "set_all_color_zones",
            DOMAIN,
            "set_state",
            {ATTR_ZONES: [0], ATTR_BRIGHTNESS: 128},
        ),
        (
            create_mock_matrix_light,
            "set_matrix_colors",
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_HS_COLOR: (120.0, 50.0)},
        ),
        (
            create_mock_infrared_light,
            "set_infrared",
            DOMAIN,
            "set_state",
            {ATTR_INFRARED: 100},
        ),
    ],
)
async def test_library_errors_become_home_assistant_errors(
    hass: HomeAssistant,
    factory: Callable[[], MockDevice],
    method: str,
    domain: str,
    service: str,
    data: dict[str, Any],
) -> None:
    """Test LifxError is translated around each public library operation."""
    device = factory()
    device.state.power = 65535
    setattr(device, method, AsyncMock(side_effect=LifxError("boom")))
    await async_setup_lifx_entry(hass, device)

    with pytest.raises(HomeAssistantError, match="boom"):
        await hass.services.async_call(
            domain,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **data},
            blocking=True,
        )


async def test_failed_refresh_marks_light_unavailable(hass: HomeAssistant) -> None:
    """Test coordinator availability remains visible on the light entity."""
    device = create_mock_light()
    await async_setup_lifx_entry(hass, device)
    device.refresh_state.side_effect = LifxError("offline")

    await async_trigger_update(hass)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "data",
    [{ATTR_INFRARED: 256}, {ATTR_ZONES: [-1]}],
)
async def test_set_state_schema_rejects_invalid_values(
    hass: HomeAssistant, data: dict[str, Any]
) -> None:
    """Test the retained set_state service schema."""
    await async_setup_lifx_entry(hass, create_mock_light())

    with pytest.raises((HomeAssistantError, vol.Invalid)):
        await hass.services.async_call(
            DOMAIN,
            "set_state",
            {ATTR_ENTITY_ID: ENTITY_ID, **data},
            blocking=True,
        )


async def test_light_starts_off(hass: HomeAssistant) -> None:
    """Test public power state zero is exposed as off."""
    await async_setup_lifx_entry(hass, create_mock_light())

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
