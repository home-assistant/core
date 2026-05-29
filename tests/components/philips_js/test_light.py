"""Tests for the Philips TV light platform."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.philips_js.light import _build_zero_pixel_layer
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


def test_build_zero_pixel_layer_returns_none_when_no_cached_data() -> None:
    """No cached data yet means we don't know the LED layout."""
    assert _build_zero_pixel_layer(None) is None
    assert _build_zero_pixel_layer({}) is None


def test_build_zero_pixel_layer_returns_none_when_all_sides_empty() -> None:
    """If every side is empty there's nothing meaningful to write."""
    cached = {"layer1": {"top": {}, "left": {}, "right": {}, "bottom": {}}}
    assert _build_zero_pixel_layer(cached) is None


def test_build_zero_pixel_layer_skips_empty_sides() -> None:
    """Empty sides (e.g. bottom: {} on TVs without bottom LEDs) are skipped.

    Including them would cause the TV to silently reject the whole payload.
    """
    cached = {
        "layer1": {
            "top": {
                "0": {"r": 255, "g": 100, "b": 50},
                "1": {"r": 200, "g": 80, "b": 40},
            },
            "left": {"0": {"r": 10, "g": 20, "b": 30}},
            "bottom": {},
        }
    }
    layer = _build_zero_pixel_layer(cached)
    assert layer is not None
    assert "bottom" not in layer
    assert set(layer) == {"top", "left"}


def test_build_zero_pixel_layer_zeros_every_pixel() -> None:
    """Every populated side gets the same indices as the input but with zero RGB."""
    cached = {
        "layer1": {
            "top": {
                "0": {"r": 255, "g": 100, "b": 50},
                "1": {"r": 200, "g": 80, "b": 40},
                "2": {"r": 0, "g": 0, "b": 0},
            },
            "right": {"0": {"r": 10, "g": 20, "b": 30}},
        }
    }
    layer = _build_zero_pixel_layer(cached)
    assert layer == {
        "top": {
            "0": {"r": 0, "g": 0, "b": 0},
            "1": {"r": 0, "g": 0, "b": 0},
            "2": {"r": 0, "g": 0, "b": 0},
        },
        "right": {"0": {"r": 0, "g": 0, "b": 0}},
    }


def test_build_zero_pixel_layer_missing_layer1_key() -> None:
    """A cached structure without a layer1 key behaves like all-empty."""
    assert (
        _build_zero_pixel_layer({"layer2": {"top": {"0": {"r": 1, "g": 1, "b": 1}}}})
        is None
    )


@pytest.fixture
async def mock_tv_quirked(mock_tv: AsyncMock) -> AsyncMock:
    """Configure mock_tv to simulate quirked firmware with cached pixels populated."""
    mock_tv.api_version = 6
    mock_tv.secured_transport = True
    mock_tv.quirk_ambilight_mode_ignored = True
    mock_tv.ambilight_cached = {
        "layer1": {
            "top": {
                "0": {"r": 100, "g": 50, "b": 25},
                "1": {"r": 0, "g": 0, "b": 0},
            },
            "left": {"0": {"r": 200, "g": 100, "b": 50}},
            "right": {"0": {"r": 30, "g": 60, "b": 90}},
            "bottom": {},
        }
    }
    mock_tv.ambilight_modes = ["internal", "manual", "expert", "lounge"]
    mock_tv.ambilight_styles = {}
    mock_tv.ambilight_mode_raw = "lounge"
    return mock_tv


@pytest.fixture
async def mock_tv_unquirked(mock_tv: AsyncMock) -> AsyncMock:
    """Configure mock_tv to simulate non-quirked firmware."""
    mock_tv.api_version = 6
    mock_tv.secured_transport = True
    mock_tv.quirk_ambilight_mode_ignored = False
    mock_tv.ambilight_modes = ["internal", "manual", "expert"]
    mock_tv.ambilight_styles = {}
    mock_tv.ambilight_mode_raw = "internal"
    return mock_tv


async def _get_light_entity_id(hass: HomeAssistant) -> str:
    """Look up the philips_js light entity id after setup."""
    light_ids = hass.states.async_entity_ids("light")
    assert light_ids, "no light entity created by philips_js setup"
    return light_ids[0]


async def test_turn_off_quirked_writes_cached_zeros(
    hass: HomeAssistant,
    mock_tv_quirked: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """On quirked firmware, light.turn_off goes through the cached-pixel path."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    light_entity = await _get_light_entity_id(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: light_entity},
        blocking=True,
    )

    # Step 1: unstick currentconfiguration with FOLLOW_VIDEO/STANDARD
    mock_tv_quirked.setAmbilightCurrentConfiguration.assert_called_with(
        {
            "styleName": "FOLLOW_VIDEO",
            "isExpert": False,
            "menuSetting": "STANDARD",
        }
    )

    # Step 2: mode flipped to expert (not internal)
    mode_calls = [
        call.args[0] for call in mock_tv_quirked.setAmbilightMode.call_args_list
    ]
    assert "expert" in mode_calls
    assert "internal" not in mode_calls

    # Step 3: cached zeros payload with the right shape
    cached_call = mock_tv_quirked.setAmbilightCached.call_args
    assert cached_call is not None
    layer = cached_call.args[0]["layer1"]
    assert "bottom" not in layer, "empty side should be skipped"
    assert layer["top"] == {
        "0": {"r": 0, "g": 0, "b": 0},
        "1": {"r": 0, "g": 0, "b": 0},
    }
    assert layer["left"] == {"0": {"r": 0, "g": 0, "b": 0}}
    assert layer["right"] == {"0": {"r": 0, "g": 0, "b": 0}}


async def test_turn_off_non_quirked_uses_legacy_path(
    hass: HomeAssistant,
    mock_tv_unquirked: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Non-quirked TVs keep using the existing setAmbilightMode('internal') path."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    light_entity = await _get_light_entity_id(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: light_entity},
        blocking=True,
    )

    # Legacy path posts setAmbilightMode('internal') and does NOT touch cached
    mock_tv_unquirked.setAmbilightMode.assert_any_call("internal")
    mock_tv_unquirked.setAmbilightCached.assert_not_called()


async def test_turn_off_quirked_raises_when_currentconfiguration_fails(
    hass: HomeAssistant,
    mock_tv_quirked: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unstick step failing surfaces as HomeAssistantError."""
    mock_tv_quirked.setAmbilightCurrentConfiguration.return_value = False
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    light_entity = await _get_light_entity_id(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: light_entity},
            blocking=True,
        )


async def test_turn_off_quirked_raises_when_mode_expert_fails(
    hass: HomeAssistant,
    mock_tv_quirked: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Switch to expert mode failing surfaces as HomeAssistantError."""
    mock_tv_quirked.setAmbilightMode.return_value = False
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    light_entity = await _get_light_entity_id(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: light_entity},
            blocking=True,
        )


async def test_turn_off_quirked_raises_when_layout_unavailable(
    hass: HomeAssistant,
    mock_tv_quirked: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Empty/missing ambilight_cached surfaces as HomeAssistantError."""
    mock_tv_quirked.ambilight_cached = None
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    light_entity = await _get_light_entity_id(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: light_entity},
            blocking=True,
        )


async def test_turn_off_quirked_raises_when_cached_write_fails(
    hass: HomeAssistant,
    mock_tv_quirked: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Cached-pixel write failing surfaces as HomeAssistantError."""
    mock_tv_quirked.setAmbilightCached.return_value = False
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    light_entity = await _get_light_entity_id(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: light_entity},
            blocking=True,
        )


async def test_turn_off_non_quirked_raises_when_mode_internal_fails(
    hass: HomeAssistant,
    mock_tv_unquirked: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """On the legacy path, setAmbilightMode('internal') returning False raises."""
    mock_tv_unquirked.setAmbilightMode.return_value = False
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    light_entity = await _get_light_entity_id(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: light_entity},
            blocking=True,
        )
