"""Tests for the integration of a twinly device."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from ttls.client import TwinklyError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    EFFECT_OFF,
    LightEntityFeature,
)
from homeassistant.components.twinkly import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .const import TEST_MAC


@pytest.mark.usefixtures("mock_twinkly_client")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the created entities."""
    with patch("homeassistant.components.twinkly.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service."""
    mock_twinkly_client.is_on.return_value = False

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.tree_1").state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1"},
        blocking=True,
    )

    mock_twinkly_client.turn_on.assert_called_once_with()


@pytest.mark.parametrize(
    ("brightness", "percent"),
    [
        pytest.param(255, 100, id="full"),
        pytest.param(84, 33, id="rounded"),
        pytest.param(5, 2, id="low"),
    ],
)
async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    brightness: int,
    percent: int,
) -> None:
    """Test support of the light.turn_on service with a brightness parameter."""
    mock_twinkly_client.is_on.return_value = False

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_BRIGHTNESS: brightness},
        blocking=True,
    )

    mock_twinkly_client.set_brightness.assert_called_once_with(percent)
    mock_twinkly_client.turn_on.assert_called_once_with()


async def test_brightness_to_zero(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with a brightness parameter."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_BRIGHTNESS: 1},
        blocking=True,
    )

    mock_twinkly_client.set_brightness.assert_not_called()
    mock_twinkly_client.turn_off.assert_called_once_with()


async def test_turn_on_with_color_rgbw(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with a rgbw parameter."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_details.return_value["led_profile"] = "RGBW"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={
            ATTR_ENTITY_ID: "light.tree_1",
            ATTR_RGBW_COLOR: (128, 64, 32, 0),
        },
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_static_colour.assert_called_once_with((0, 128, 64, 32))
    mock_twinkly_client.set_mode.assert_called_once_with("color")
    assert mock_twinkly_client.default_mode == "color"


async def test_turn_on_with_color_rgb(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with a rgb parameter."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_details.return_value["led_profile"] = "RGB"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_RGB_COLOR: (128, 64, 32)},
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_static_colour.assert_called_once_with((128, 64, 32))
    mock_twinkly_client.set_mode.assert_called_once_with("color")
    assert mock_twinkly_client.default_mode == "color"


async def test_turn_on_with_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with effects."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_details.return_value["led_profile"] = "RGB"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: "2 Rainbow"},
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_current_movie.assert_called_once_with(2)
    mock_twinkly_client.set_mode.assert_called_once_with("movie")
    assert mock_twinkly_client.default_mode == "movie"


async def test_color_mode_reports_effect_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test that a solid color reports off even when a movie id is remembered."""
    await setup_integration(hass, mock_config_entry)

    attributes = hass.states.get("light.tree_1").attributes
    assert attributes[ATTR_EFFECT] == EFFECT_OFF
    assert attributes[ATTR_EFFECT_LIST][0] == EFFECT_OFF


async def test_turn_on_reapplies_current_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test that the current movie is sent again after a solid color."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("light.tree_1").attributes[ATTR_EFFECT] == EFFECT_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: "1 Rainbow"},
        blocking=True,
    )

    mock_twinkly_client.set_current_movie.assert_called_once_with(1)
    mock_twinkly_client.set_mode.assert_called_once_with("movie")
    assert mock_twinkly_client.default_mode == "movie"


@pytest.mark.parametrize("mode", ["color", "rt"])
async def test_turn_on_with_current_movie_in_other_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    mode: str,
) -> None:
    """Test selecting the current movie switches to movie mode from another mode."""
    mock_twinkly_client.get_mode.return_value = {"mode": mode}

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: "1 Rainbow"},
        blocking=True,
    )

    mock_twinkly_client.set_current_movie.assert_called_once_with(1)
    mock_twinkly_client.set_mode.assert_called_once_with("movie")
    assert mock_twinkly_client.default_mode == "movie"


async def test_turn_on_with_current_movie_in_movie_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test selecting the movie already playing sends nothing."""
    mock_twinkly_client.get_mode.return_value = {"mode": "movie"}

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: "1 Rainbow"},
        blocking=True,
    )

    mock_twinkly_client.set_current_movie.assert_not_called()
    mock_twinkly_client.set_mode.assert_not_called()


@pytest.mark.parametrize(
    ("led_profile", "data"),
    [
        ("RGBW", {ATTR_RGBW_COLOR: (128, 64, 32, 0)}),
        ("RGB", {ATTR_RGB_COLOR: (128, 64, 32)}),
    ],
)
@pytest.mark.parametrize(
    ("mode", "expected_mode_calls", "expected_movie_calls"),
    [
        pytest.param("movie", [], [], id="movie_playing"),
        pytest.param("color", [call("movie")], [call(1)], id="from_color"),
    ],
)
async def test_turn_on_with_color_and_movie(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    led_profile: str,
    data: dict[str, Any],
    mode: str,
    expected_mode_calls: list[Any],
    expected_movie_calls: list[Any],
) -> None:
    """Test a movie wins over a color sent in the same call, as scenes do."""
    mock_twinkly_client.get_mode.return_value = {"mode": mode}
    mock_twinkly_client.get_details.return_value["led_profile"] = led_profile

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: "1 Rainbow"} | data,
        blocking=True,
    )

    mock_twinkly_client.set_static_colour.assert_not_called()
    assert mock_twinkly_client.set_mode.call_args_list == expected_mode_calls
    assert mock_twinkly_client.set_current_movie.call_args_list == expected_movie_calls


@pytest.mark.parametrize(
    ("mode", "expected_mode_calls"),
    [
        pytest.param("movie", [call("color")], id="from_movie"),
        pytest.param("color", [], id="already_shown"),
    ],
)
async def test_turn_on_with_current_color(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    mode: str,
    expected_mode_calls: list[Any],
) -> None:
    """Test the color the device holds is only sent when it is not shown."""
    mock_twinkly_client.get_mode.return_value = {"mode": mode}

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_RGB_COLOR: (255, 255, 255)},
        blocking=True,
    )

    assert mock_twinkly_client.set_mode.call_args_list == expected_mode_calls


async def test_turn_on_with_color_and_no_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test a color with effect off switches to color mode once."""
    mock_twinkly_client.get_mode.return_value = {"mode": "movie"}

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={
            ATTR_ENTITY_ID: "light.tree_1",
            ATTR_RGB_COLOR: (128, 64, 32),
            ATTR_EFFECT: EFFECT_OFF,
        },
        blocking=True,
    )

    mock_twinkly_client.set_static_colour.assert_called_once_with((128, 64, 32))
    mock_twinkly_client.set_mode.assert_called_once_with("color")
    mock_twinkly_client.set_current_movie.assert_not_called()


@pytest.mark.parametrize("effect", [EFFECT_OFF, "None", "none"])
async def test_turn_on_with_no_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    effect: str,
) -> None:
    """Test that off, including the old None name, selects a solid color."""
    mock_twinkly_client.get_mode.return_value = {"mode": "movie"}

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: effect},
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_mode.assert_called_once_with("color")
    assert mock_twinkly_client.default_mode == "color"
    mock_twinkly_client.set_current_movie.assert_not_called()


@pytest.mark.parametrize(
    ("data"),
    [
        {ATTR_RGBW_COLOR: (128, 64, 32, 0)},
        {ATTR_RGB_COLOR: (128, 64, 32)},
    ],
)
async def test_turn_on_with_missing_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    data: dict[str, Any],
) -> None:
    """Test light.turn_on with rgbw color and missing effect support."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_firmware_version.return_value["version"] = "2.7.0"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        ^ hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1"} | data,
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_cycle_colours.assert_called_once_with((128, 64, 32))
    mock_twinkly_client.set_mode.assert_called_once_with("movie")
    assert mock_twinkly_client.default_mode == "movie"
    mock_twinkly_client.set_current_movie.assert_not_called()


async def test_turn_on_with_color_rgbw_and_missing_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with missing effect support."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_firmware_version.return_value["version"] = "2.7.0"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        ^ hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: "2 Rainbow"},
        blocking=True,
    )

    mock_twinkly_client.set_current_movie.assert_not_called()


async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_off service."""

    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "light.tree_1"},
        blocking=True,
    )
    mock_twinkly_client.turn_off.assert_called_once_with()


async def test_no_current_movie(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the last known movie is kept when it cannot be read."""
    mock_twinkly_client.get_mode.return_value = {"mode": "movie"}

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.tree_1").attributes[ATTR_EFFECT] == "1 Rainbow"

    mock_twinkly_client.get_current_movie.side_effect = TwinklyError

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("light.tree_1").state != STATE_UNAVAILABLE
    assert hass.states.get("light.tree_1").attributes[ATTR_EFFECT] == "1 Rainbow"


@pytest.mark.parametrize(
    ("led_profile", "color", "attribute", "expected"),
    [
        pytest.param(
            "RGB",
            {"red": 255, "green": 98, "blue": 13},
            ATTR_RGB_COLOR,
            (255, 98, 13),
            id="rgb",
        ),
        pytest.param(
            "RGBW",
            {"red": 255, "green": 98, "blue": 13, "white": 40},
            ATTR_RGBW_COLOR,
            (255, 98, 13, 40),
            id="rgbw",
        ),
        pytest.param(
            "RGBW",
            {"red": 255, "green": 98, "blue": 13},
            ATTR_RGBW_COLOR,
            (255, 255, 255, 0),
            id="rgbw_without_white",
        ),
    ],
)
async def test_color_read_from_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    led_profile: str,
    color: dict[str, int],
    attribute: str,
    expected: tuple[int, ...],
) -> None:
    """Test the color shown is the one stored on the device."""
    mock_twinkly_client.get_details.return_value["led_profile"] = led_profile
    mock_twinkly_client.get_current_colour.return_value = color | {"code": 1000}

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.tree_1").attributes[attribute] == expected


async def test_color_read_failure_keeps_last_color(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the last known color is kept when it cannot be read."""
    mock_twinkly_client.get_current_colour.return_value = {
        "red": 255,
        "green": 98,
        "blue": 13,
        "code": 1000,
    }

    await setup_integration(hass, mock_config_entry)

    mock_twinkly_client.get_current_colour.side_effect = TwinklyError

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("light.tree_1").attributes[ATTR_RGB_COLOR] == (255, 98, 13)


async def test_update_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Validate device's name update behavior.

    Validate that if device name is changed from the Twinkly app,
    then the name of the entity is updated and it's also persisted,
    so it can be restored when starting HA while Twinkly is offline.
    """

    await setup_integration(hass, mock_config_entry)

    dev_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_MAC), mock_config_entry.entry_id
    )

    assert dev_entry.name == "Tree 1"

    mock_twinkly_client.get_details.return_value["device_name"] = "new_device_name"

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    dev_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_MAC), mock_config_entry.entry_id
    )

    assert dev_entry.name == "new_device_name"
