"""Test for the SmartThings light platform."""

from typing import Any
from unittest.mock import AsyncMock, call

from pysmartthings.models import Capability, Command
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities

from tests.common import MockConfigEntry


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


@pytest.mark.parametrize("fixture", ["hue_rgbw_color_bulb"])
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
                    argument=4000,
                ),
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH,
                    Command.ON,
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
                    argument={"hue": 97.2222, "saturation": 90.0},
                ),
                call(
                    "cb958955-b015-498c-9e62-fc0c51abd054",
                    Capability.SWITCH,
                    Command.ON,
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


@pytest.mark.parametrize("fixture", ["hue_rgbw_color_bulb"])
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
