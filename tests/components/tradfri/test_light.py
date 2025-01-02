"""Tradfri lights platform tests."""

from typing import Any

import pytest
from pytradfri.const import ATTR_DEVICE_STATE, ATTR_LIGHT_CONTROL, ATTR_REACHABLE_STATE
from pytradfri.device import Device

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.components.tradfri.const import DOMAIN
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from .common import CommandStore, setup_integration

from tests.common import load_fixture


@pytest.fixture(scope="module")
def bulb_w() -> str:
    """Return a bulb W response."""
    return load_fixture("bulb_w.json", DOMAIN)


@pytest.fixture(scope="module")
def bulb_ws() -> str:
    """Return a bulb WS response."""
    return load_fixture("bulb_ws.json", DOMAIN)


@pytest.fixture(scope="module")
def bulb_cws() -> str:
    """Return a bulb CWS response."""
    return load_fixture("bulb_cws.json", DOMAIN)


@pytest.mark.parametrize(
    ("device", "entity_id", "state_attributes"),
    [
        (
            "bulb_w",
            "light.test_w",
            {
                ATTR_BRIGHTNESS: 250,
                ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
                ATTR_COLOR_MODE: ColorMode.BRIGHTNESS,
            },
        ),
        (
            "bulb_ws",
            "light.test_ws",
            {
                ATTR_BRIGHTNESS: 250,
                ATTR_COLOR_TEMP_KELVIN: 2500,
                ATTR_MAX_COLOR_TEMP_KELVIN: 4000,
                ATTR_MIN_COLOR_TEMP_KELVIN: 2202,
                ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
                ATTR_COLOR_MODE: ColorMode.COLOR_TEMP,
            },
        ),
        (
            "bulb_cws",
            "light.test_cws",
            {
                ATTR_BRIGHTNESS: 250,
                ATTR_HS_COLOR: (29.812, 65.252),
                ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
                ATTR_COLOR_MODE: ColorMode.HS,
            },
        ),
    ],
    indirect=["device"],
)
async def test_light_state(
    hass: HomeAssistant,
    device: Device,
    entity_id: str,
    state_attributes: dict[str, Any],
) -> None:
    """Test light state."""
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    for key, value in state_attributes.items():
        assert state.attributes[key] == value


@pytest.mark.parametrize("device", ["bulb_w"], indirect=True)
async def test_light_available(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
) -> None:
    """Test light available property."""
    entity_id = "light.test_w"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    await command_store.trigger_observe_callback(
        hass, device, {ATTR_REACHABLE_STATE: 0}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "transition",
    [{}, {"transition": 0}, {"transition": 1}],
    ids=["transition_none", "transition_0", "transition_1"],
)
@pytest.mark.parametrize(
    ("device", "entity_id", "service_data", "state_attributes"),
    [
        # turn_on
        (
            "bulb_w",
            "light.test_w",
            {},
            {},
        ),
        # brightness > 0
        (
            "bulb_w",
            "light.test_w",
            {"brightness": 100},
            {"brightness": 100},
        ),
        # brightness == 1
        (
            "bulb_w",
            "light.test_w",
            {"brightness": 1},
            {"brightness": 1},
        ),
        # brightness > 254
        (
            "bulb_w",
            "light.test_w",
            {"brightness": 1000},
            {"brightness": 254},
        ),
        # color_temp
        (
            "bulb_ws",
            "light.test_ws",
            {"color_temp": 250},
            {"color_temp": 250},
        ),
        # color_temp < 250
        (
            "bulb_ws",
            "light.test_ws",
            {"color_temp": 1},
            {"color_temp": 250},
        ),
        # color_temp > 454
        (
            "bulb_ws",
            "light.test_ws",
            {"color_temp": 1000},
            {"color_temp": 454},
        ),
        # hs_color
        (
            "bulb_cws",
            "light.test_cws",
            {"hs_color": [300, 100]},
            {"hs_color": [300, 100]},
        ),
        # ct + brightness
        (
            "bulb_ws",
            "light.test_ws",
            {"color_temp": 250, "brightness": 200},
            {"color_temp": 250, "brightness": 200},
        ),
        # ct + brightness (no temp support)
        (
            "bulb_cws",
            "light.test_cws",
            {"color_temp": 250, "brightness": 200},
            {"hs_color": [26.807, 34.869], "brightness": 200},
        ),
        # ct + brightness (no temp or color support)
        (
            "bulb_w",
            "light.test_w",
            {"color_temp": 250, "brightness": 200},
            {"brightness": 200},
        ),
        # hs + brightness
        (
            "bulb_cws",
            "light.test_cws",
            {"hs_color": [300, 100], "brightness": 200},
            {"hs_color": [300, 100], "brightness": 200},
        ),
    ],
    indirect=["device"],
    ids=[
        "turn_on",
        "brightness > 0",
        "brightness == 1",
        "brightness > 254",
        "color_temp",
        "color_temp < 250",
        "color_temp > 454",
        "hs_color",
        "ct + brightness",
        "ct + brightness (no temp support)",
        "ct + brightness (no temp or color support)",
        "hs + brightness",
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
    entity_id: str,
    service_data: dict[str, Any],
    transition: dict[str, int],
    state_attributes: dict[str, Any],
) -> None:
    """Test turning on a light."""
    # Make sure the light is off.
    device.raw[ATTR_LIGHT_CONTROL][0][ATTR_DEVICE_STATE] = 0
    await setup_integration(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id, **service_data, **transition},
        blocking=True,
    )
    await hass.async_block_till_done()

    await command_store.trigger_observe_callback(
        hass, device, {ATTR_LIGHT_CONTROL: [{ATTR_DEVICE_STATE: 1}]}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    for key, value in state_attributes.items():
        # Allow some rounding error in color conversions.
        assert state.attributes[key] == pytest.approx(value, abs=0.01)


@pytest.mark.parametrize(
    "transition",
    [{}, {"transition": 0}, {"transition": 1}],
    ids=["transition_none", "transition_0", "transition_1"],
)
@pytest.mark.parametrize(
    ("device", "entity_id"),
    [
        ("bulb_w", "light.test_w"),
        ("bulb_ws", "light.test_ws"),
        ("bulb_cws", "light.test_cws"),
    ],
    indirect=["device"],
)
async def test_turn_off(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
    entity_id: str,
    transition: dict[str, int],
) -> None:
    """Test turning off a light."""
    await setup_integration(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id, **transition},
        blocking=True,
    )
    await hass.async_block_till_done()

    await command_store.trigger_observe_callback(
        hass, device, {ATTR_LIGHT_CONTROL: [{ATTR_DEVICE_STATE: 0}]}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
