"""Test for the SmartThings light platform."""

from typing import Any
from unittest.mock import AsyncMock, call

from pysmartthings import Attribute, Capability, Command
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.components.smartthings.const import MAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_update,
)

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.LIGHT)


@pytest.mark.parametrize("device_fixture", ["hue_rgbw_color_bulb"])
@pytest.mark.parametrize(
    ("data", "calls"),
    [
        (
            {},
            [
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH,
                    Command.ON,
                    MAIN,
                )
            ],
        ),
        (
            {ATTR_COLOR_TEMP_KELVIN: 4000},
            [
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.COLOR_TEMPERATURE,
                    Command.SET_COLOR_TEMPERATURE,
                    MAIN,
                    argument=4000,
                ),
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH,
                    Command.ON,
                    MAIN,
                ),
            ],
        ),
        (
            {ATTR_HS_COLOR: [350, 90]},
            [
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.COLOR_CONTROL,
                    Command.SET_COLOR,
                    MAIN,
                    argument={"hue": 97.2222, "saturation": 90.0},
                ),
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH,
                    Command.ON,
                    MAIN,
                ),
            ],
        ),
        (
            {ATTR_BRIGHTNESS: 50},
            [
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH_LEVEL,
                    Command.SET_LEVEL,
                    MAIN,
                    argument=[20, 0],
                )
            ],
        ),
        (
            {ATTR_BRIGHTNESS: 50, ATTR_TRANSITION: 3},
            [
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH_LEVEL,
                    Command.SET_LEVEL,
                    MAIN,
                    argument=[20, 3],
                )
            ],
        ),
    ],
)
async def test_turn_on_light(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    data: dict[str, Any],
    calls: list[call],
) -> None:
    """Test light turn on command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.standing_light"} | data,
        blocking=True,
    )
    assert devices.execute_device_command.mock_calls == calls


@pytest.mark.parametrize("device_fixture", ["hue_rgbw_color_bulb"])
@pytest.mark.parametrize(
    ("data", "calls"),
    [
        (
            {},
            [
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH,
                    Command.OFF,
                    MAIN,
                )
            ],
        ),
        (
            {ATTR_TRANSITION: 3},
            [
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH_LEVEL,
                    Command.SET_LEVEL,
                    MAIN,
                    argument=[0, 3],
                )
            ],
        ),
    ],
)
async def test_turn_off_light(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    data: dict[str, Any],
    calls: list[call],
) -> None:
    """Test light turn off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.standing_light"} | data,
        blocking=True,
    )
    assert devices.execute_device_command.mock_calls == calls


@pytest.mark.parametrize("device_fixture", ["hue_rgbw_color_bulb"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.standing_light").state == STATE_OFF

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.SWITCH,
        Attribute.SWITCH,
        "on",
    )

    assert hass.states.get("light.standing_light").state == STATE_ON


@pytest.mark.parametrize("device_fixture", ["hue_rgbw_color_bulb"])
async def test_updating_brightness(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test brightness update."""
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.COLOR_CONTROL,
        Attribute.HUE,
        40,
    )

    assert hass.states.get("light.standing_light").attributes[ATTR_BRIGHTNESS] == 178

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.SWITCH_LEVEL,
        Attribute.LEVEL,
        20,
    )

    assert hass.states.get("light.standing_light").attributes[ATTR_BRIGHTNESS] == 51


@pytest.mark.parametrize("device_fixture", ["hue_rgbw_color_bulb"])
async def test_updating_hs(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test hue/saturation update."""
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.COLOR_CONTROL,
        Attribute.HUE,
        40,
    )

    assert hass.states.get("light.standing_light").attributes[ATTR_HS_COLOR] == (
        144.0,
        60,
    )

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.COLOR_CONTROL,
        Attribute.HUE,
        20,
    )

    assert hass.states.get("light.standing_light").attributes[ATTR_HS_COLOR] == (
        72.0,
        60,
    )


@pytest.mark.parametrize("device_fixture", ["hue_rgbw_color_bulb"])
async def test_updating_color_temp(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test color temperature update."""
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.COLOR_TEMPERATURE,
        Attribute.COLOR_TEMPERATURE,
        3000,
    )

    assert (
        hass.states.get("light.standing_light").attributes[ATTR_COLOR_MODE]
        is ColorMode.COLOR_TEMP
    )
    assert (
        hass.states.get("light.standing_light").attributes[ATTR_COLOR_TEMP_KELVIN]
        == 3000
    )

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.COLOR_TEMPERATURE,
        Attribute.COLOR_TEMPERATURE,
        2000,
    )

    assert (
        hass.states.get("light.standing_light").attributes[ATTR_COLOR_TEMP_KELVIN]
        == 2000
    )


@pytest.mark.parametrize("device_fixture", ["hue_rgbw_color_bulb"])
async def test_color_modes(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test color mode changes."""
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")
    set_attribute_value(devices, Capability.COLOR_CONTROL, Attribute.SATURATION, 50)
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("light.standing_light").attributes[ATTR_COLOR_MODE]
        is ColorMode.HS
    )

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.COLOR_TEMPERATURE,
        Attribute.COLOR_TEMPERATURE,
        2000,
    )

    assert (
        hass.states.get("light.standing_light").attributes[ATTR_COLOR_MODE]
        is ColorMode.COLOR_TEMP
    )

    await trigger_update(
        hass,
        devices,
        "cb958955-b015-498c-9e62-fc0c51abd054",
        Capability.COLOR_CONTROL,
        Attribute.HUE,
        20,
    )

    assert (
        hass.states.get("light.standing_light").attributes[ATTR_COLOR_MODE]
        is ColorMode.HS
    )


@pytest.mark.parametrize("device_fixture", ["hue_rgbw_color_bulb"])
async def test_color_mode_after_startup(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test color mode after startup."""
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")

    RESTORE_DATA = {
        ATTR_BRIGHTNESS: 178,
        ATTR_COLOR_MODE: ColorMode.COLOR_TEMP,
        ATTR_COLOR_TEMP_KELVIN: 3000,
        ATTR_HS_COLOR: (144.0, 60),
        ATTR_MAX_COLOR_TEMP_KELVIN: 9000,
        ATTR_MIN_COLOR_TEMP_KELVIN: 2000,
        ATTR_RGB_COLOR: (255, 128, 0),
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP, ColorMode.HS],
        ATTR_XY_COLOR: (0.61, 0.35),
    }

    mock_restore_cache_with_extra_data(
        hass, ((State("light.standing_light", STATE_ON), RESTORE_DATA),)
    )
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("light.standing_light").attributes[ATTR_COLOR_MODE]
        is ColorMode.COLOR_TEMP
    )
