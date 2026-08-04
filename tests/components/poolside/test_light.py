"""Tests for Poolside LIGHT controls."""

from aiopoolside import PoolsideControl
from aiopoolside.const import ControlType
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_EFFECT,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import FakePoolsideClient, make_control

RGB_LIGHT_UUID = "light-rgb"
DIM_LIGHT_UUID = "light-dim"
RGB_ENTITY_ID = "light.pool_pool_light"
DIM_ENTITY_ID = "light.pool_spa_light"
DEFAULT_COLOR = "Ocean Blue"
COMBINED_LIGHT_UUID = "light-combined"
COMBINED_ENTITY_ID = "light.pool_combined_light"
COMBINED_MEMBER_UUID = "light-combined-member-a"


@pytest.fixture
def controls() -> list[PoolsideControl]:
    """One color/light-show-capable light, one brightness-only, one combined."""
    return [
        make_control(
            RGB_LIGHT_UUID,
            "Pool Light",
            ControlType.LIGHT,
            SupportsColors=True,
            DefaultColor=DEFAULT_COLOR,
        ),
        make_control(
            DIM_LIGHT_UUID, "Spa Light", ControlType.LIGHT, SupportsColors=False
        ),
        make_control(
            COMBINED_LIGHT_UUID,
            "Combined Light",
            ControlType.LIGHT,
            SupportsColors=True,
            DefaultColor=DEFAULT_COLOR,
            MemberControlUUIDs=[COMBINED_MEMBER_UUID, "light-combined-member-b"],
        ),
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_state_and_brightness(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Brightness is converted from the device's 0-100 scale to HA's 0-255."""
    fake_client.set_status(RGB_LIGHT_UUID, "Status", "ON")
    fake_client.set_status(RGB_LIGHT_UUID, "Brightness", 50)
    await hass.async_block_till_done()

    state = hass.states.get(RGB_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == round(50 / 100 * 255)


@pytest.mark.usefixtures("setup_integration")
async def test_effect_only_when_supported(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Only the color/show-capable light exposes an effect list and effect."""
    fake_client.set_status(RGB_LIGHT_UUID, "Status", "ON")
    fake_client.set_status(RGB_LIGHT_UUID, "LightName", "Sunset")
    fake_client.set_status(DIM_LIGHT_UUID, "Status", "ON")
    await hass.async_block_till_done()

    rgb_state = hass.states.get(RGB_ENTITY_ID)
    dim_state = hass.states.get(DIM_ENTITY_ID)
    assert rgb_state is not None
    assert dim_state is not None
    assert rgb_state.attributes[ATTR_EFFECT] == "Sunset"
    assert "effect_list" not in dim_state.attributes
    assert ATTR_EFFECT not in dim_state.attributes


@pytest.mark.usefixtures("setup_integration")
async def test_effect_list_combines_shows_and_colors(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """The effect list is the union of the controller's shows and colors catalogs.

    The catalogs arrive as JSON-encoded strings, not native JSON arrays.
    """
    fake_client.set_status(
        RGB_LIGHT_UUID, "AvailableShows", '[\n  "Party Mode",\n  "Romance Mode"\n]'
    )
    fake_client.set_status(RGB_LIGHT_UUID, "AvailableColors", '["Blue", "Green"]')
    await hass.async_block_till_done()

    state = hass.states.get(RGB_ENTITY_ID)
    assert state is not None
    assert state.attributes["effect_list"] == [
        "Blue",
        "Green",
        "Party Mode",
        "Romance Mode",
    ]


@pytest.mark.parametrize(
    ("shows", "colors"),
    [
        pytest.param(None, None, id="not-yet-received"),
        pytest.param("[]", "[]", id="empty-catalogs"),
        pytest.param("not json", '{"Blue": 1}', id="unusable-payloads"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_effect_list_none_without_usable_catalog(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    shows: str | None,
    colors: str | None,
) -> None:
    """Missing, empty, or unusable catalogs yield no effect list."""
    fake_client.set_status(RGB_LIGHT_UUID, "AvailableShows", shows)
    fake_client.set_status(RGB_LIGHT_UUID, "AvailableColors", colors)
    await hass.async_block_till_done()

    state = hass.states.get(RGB_ENTITY_ID)
    assert state is not None
    assert state.attributes["effect_list"] is None


@pytest.mark.usefixtures("setup_integration")
async def test_non_dimmable_light_is_on_off_with_effects(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """SupportsBrightness=false makes the light on/off only, keeping color selection."""
    fake_client.set_status(RGB_LIGHT_UUID, "Status", "ON")
    fake_client.set_status(RGB_LIGHT_UUID, "Brightness", 50)
    fake_client.set_status(RGB_LIGHT_UUID, "SupportsBrightness", "false")
    fake_client.set_status(RGB_LIGHT_UUID, "AvailableColors", '["Blue", "Green"]')
    await hass.async_block_till_done()

    state = hass.states.get(RGB_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.ONOFF
    assert ATTR_BRIGHTNESS not in state.attributes
    assert state.attributes["effect_list"] == ["Blue", "Green"]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: RGB_ENTITY_ID, ATTR_EFFECT: "Blue"},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        RGB_LIGHT_UUID,
        Status="ON",
        Brightness="100",
        Speed="0",
        Twinkle="0",
        LightName="Blue",
    )


@pytest.mark.usefixtures("setup_integration")
async def test_dimmable_light_defaults_to_brightness_mode(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """SupportsBrightness=true (and unknown) exposes the brightness color mode."""
    fake_client.set_status(RGB_LIGHT_UUID, "SupportsBrightness", "true")
    await hass.async_block_till_done()

    state = hass.states.get(RGB_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]


@pytest.mark.parametrize(
    ("increments", "requested", "written"),
    [
        pytest.param("[25, 50, 75, 100]", 90, "25", id="snaps-down-to-nearest"),
        pytest.param("[25, 50, 75, 100]", 160, "75", id="snaps-up-to-nearest"),
        pytest.param("[25, 50, 75, 100]", 1, "25", id="never-below-lowest-level"),
        pytest.param("[]", 128, "50", id="empty-increments-unconstrained"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_turn_on_snaps_brightness_to_increments(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    increments: str,
    requested: int,
    written: str,
) -> None:
    """Requested brightness is snapped to the nearest controller-allowed level."""
    fake_client.set_status(RGB_LIGHT_UUID, "BrightnessIncrements", increments)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: RGB_ENTITY_ID, ATTR_BRIGHTNESS: requested},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        RGB_LIGHT_UUID,
        Status="ON",
        Brightness=written,
        Speed="0",
        Twinkle="0",
        LightName=DEFAULT_COLOR,
    )


@pytest.mark.usefixtures("setup_integration")
async def test_turn_on_writes_full_state(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Turning on writes brightness/speed/twinkle/effect together, never a delta."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: RGB_ENTITY_ID,
            ATTR_BRIGHTNESS: 128,
            ATTR_EFFECT: "Sunset",
        },
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        RGB_LIGHT_UUID,
        Status="ON",
        Brightness=str(round(128 / 255 * 100)),
        Speed="0",
        Twinkle="0",
        LightName="Sunset",
    )


@pytest.mark.usefixtures("setup_integration")
async def test_turn_on_without_kwargs_preserves_previous_state(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Turning on with no new values re-sends the light's last known full state."""
    fake_client.set_status(RGB_LIGHT_UUID, "Brightness", 60)
    fake_client.set_status(RGB_LIGHT_UUID, "LightName", "Party")
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: RGB_ENTITY_ID},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        RGB_LIGHT_UUID,
        Status="ON",
        Brightness="60",
        Speed="0",
        Twinkle="0",
        LightName="Party",
    )


@pytest.mark.usefixtures("setup_integration")
async def test_turn_on_never_sends_zero_brightness(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """A very low HA brightness never rounds down to 0 (the controller treats 0 as 100)."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DIM_ENTITY_ID, ATTR_BRIGHTNESS: 1},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        DIM_LIGHT_UUID,
        Status="ON",
        Brightness="1",
        Speed="0",
        Twinkle="0",
    )


@pytest.mark.usefixtures("setup_integration")
async def test_combined_light_reflects_member_status_push(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """A combined light picks up status pushed under a member's UUID too.

    Physical member fixtures may report their own real state independently
    under their own UUID rather than the synthetic combined UUID.
    """
    fake_client.set_status(COMBINED_MEMBER_UUID, "ActualPowerState", "ON")
    await hass.async_block_till_done()

    state = hass.states.get(COMBINED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_integration")
async def test_turn_off(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Turning off sends only Status=OFF."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DIM_ENTITY_ID},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        DIM_LIGHT_UUID, Status="OFF"
    )
    assert hass.states.get(DIM_ENTITY_ID) is not None
