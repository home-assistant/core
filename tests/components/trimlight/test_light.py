"""Tests for the Trimlight light platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from aiotrimlight import TrimlightConnectionError, TrimlightICType, TrimlightLightState
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.components.trimlight.const import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ENTITY_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    "ic_type",
    [
        pytest.param(TrimlightICType.RGB, id="rgb"),
        pytest.param(TrimlightICType.RGBW, id="rgbw"),
        pytest.param(TrimlightICType.RGBCW, id="rgbww"),
    ],
)
async def test_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test IC-specific capabilities, read colors, and the entity registration."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "on", "initial_is_on", "expected_state"),
    [
        pytest.param(SERVICE_TURN_ON, True, False, STATE_ON, id="on"),
        pytest.param(SERVICE_TURN_OFF, False, True, STATE_OFF, id="off"),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_trimlight: MagicMock,
    service: str,
    on: bool,
    expected_state: str,
) -> None:
    """Test power actions change the opposite state optimistically."""
    assert hass.states.get(ENTITY_ID).state != expected_state

    await hass.services.async_call(
        LIGHT_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_trimlight.set_light_state.assert_awaited_once_with(
        on=on,
        brightness=None,
        red=None,
        green=None,
        blue=None,
        warm_white=None,
        cold_white=None,
    )
    assert hass.states.get(ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("ic_type", "attribute", "color", "warm_white", "cold_white"),
    [
        pytest.param(
            TrimlightICType.RGB, ATTR_RGB_COLOR, (40, 50, 60), None, None, id="rgb"
        ),
        pytest.param(
            TrimlightICType.RGBW, ATTR_RGBW_COLOR, (40, 50, 60, 70), 70, None, id="rgbw"
        ),
        pytest.param(
            TrimlightICType.RGBCW,
            ATTR_RGBWW_COLOR,
            (40, 50, 60, 70, 80),
            80,
            70,
            id="rgbww",
        ),
    ],
)
async def test_color(
    hass: HomeAssistant,
    mock_trimlight: MagicMock,
    attribute: str,
    color: tuple[int, ...],
    warm_white: int | None,
    cold_white: int | None,
) -> None:
    """Test brightness and native colors, including RGBWW cold/warm ordering."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 80, attribute: color},
        blocking=True,
    )

    mock_trimlight.set_light_state.assert_awaited_once_with(
        on=True,
        brightness=80,
        red=40,
        green=50,
        blue=60,
        warm_white=warm_white,
        cold_white=cold_white,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_BRIGHTNESS] == 80
    assert state.attributes[attribute] == color


async def test_brightness_and_poll(
    hass: HomeAssistant,
    mock_trimlight: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test immediate optimistic brightness, unchanged colors, and poll calibration."""

    async def check_optimistic_state(**kwargs: bool | int | None) -> None:
        # The target must be visible before the client finishes writing it.
        assert hass.states.get(ENTITY_ID).attributes[ATTR_BRIGHTNESS] == 80

    mock_trimlight.set_light_state.side_effect = check_optimistic_state
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 80},
        blocking=True,
    )

    mock_trimlight.set_light_state.assert_awaited_once_with(
        on=True,
        brightness=80,
        red=None,
        green=None,
        blue=None,
        warm_white=None,
        cold_white=None,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_RGB_COLOR] == (10, 20, 30)
    mock_trimlight.get_light_state.assert_awaited_once_with()

    mock_trimlight.get_light_state.return_value = replace(
        mock_trimlight.get_light_state.return_value, brightness=64
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_trimlight.get_light_state.await_count == 2
    assert hass.states.get(ENTITY_ID).attributes[ATTR_BRIGHTNESS] == 64


@pytest.mark.parametrize(
    ("ic_type", "attribute"),
    [
        pytest.param(TrimlightICType.RGB, ATTR_RGB_COLOR, id="rgb"),
        pytest.param(TrimlightICType.RGBW, ATTR_RGBW_COLOR, id="rgbw"),
        pytest.param(TrimlightICType.RGBCW, ATTR_RGBWW_COLOR, id="rgbww"),
    ],
)
async def test_unknown_output(
    hass: HomeAssistant,
    mock_trimlight: MagicMock,
    freezer: FrozenDateTimeFactory,
    attribute: str,
) -> None:
    """Test non-static output clears attributes and brightness cannot identify colors."""
    mock_trimlight.get_light_state.return_value = TrimlightLightState(is_on=True)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] is ColorMode.UNKNOWN
    assert state.attributes[ATTR_BRIGHTNESS] is None
    assert state.attributes[attribute] is None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 80},
        blocking=True,
    )
    mock_trimlight.set_light_state.assert_awaited_once_with(
        on=True,
        brightness=80,
        red=None,
        green=None,
        blue=None,
        warm_white=None,
        cold_white=None,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_COLOR_MODE] is ColorMode.UNKNOWN


@pytest.mark.parametrize(
    ("ic_type", "attribute", "warm_white", "cold_white"),
    [
        pytest.param(
            TrimlightICType.RGBW,
            ATTR_RGBW_COLOR,
            None,
            50,
            id="rgbw",
        ),
        pytest.param(
            TrimlightICType.RGBCW,
            ATTR_RGBWW_COLOR,
            40,
            None,
            id="rgbww",
        ),
    ],
)
async def test_missing_white_channel(
    hass: HomeAssistant,
    mock_trimlight: MagicMock,
    freezer: FrozenDateTimeFactory,
    attribute: str,
    warm_white: int | None,
    cold_white: int | None,
) -> None:
    """Test a missing native white channel makes the color mode unknown."""
    mock_trimlight.get_light_state.return_value = replace(
        mock_trimlight.get_light_state.return_value,
        warm_white=warm_white,
        cold_white=cold_white,
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_COLOR_MODE] is ColorMode.UNKNOWN
    assert state.attributes[attribute] is None


async def test_unavailable_and_recovery(
    hass: HomeAssistant,
    mock_trimlight: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test polling errors mark the entity unavailable until a successful poll."""
    mock_trimlight.get_light_state.side_effect = TrimlightConnectionError(
        "request failed"
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_trimlight.get_light_state.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_command_error(
    hass: HomeAssistant,
    mock_trimlight: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test write errors reach the user and polling corrects the optimistic target."""
    mock_trimlight.set_light_state.side_effect = TrimlightConnectionError(
        "request failed"
    )

    with pytest.raises(
        HomeAssistantError,
        match="Failed to control Test controller: request failed",
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_RGB_COLOR: (40, 50, 60)},
            blocking=True,
        )

    assert hass.states.get(ENTITY_ID).attributes[ATTR_RGB_COLOR] == (40, 50, 60)
    mock_trimlight.get_light_state.assert_awaited_once_with()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_RGB_COLOR] == (10, 20, 30)
    assert mock_trimlight.set_light_state.await_count == 1
