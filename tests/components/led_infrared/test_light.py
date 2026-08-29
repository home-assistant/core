"""Tests for the LED Infrared light platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.led import (
    Generic13KeyCode,
    Generic24KeyCode,
    Generic40KeyCode,
    Generic44KeyCode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.led_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    LEDIrDeviceType,
)
from homeassistant.components.light import (
    ATTR_EFFECT,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import LIGHT_ENTITY_ID, LEDIrKeyCode

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture(autouse=True)
def light_only() -> Generator[None]:
    """Enable only the light platform."""
    with patch(
        "homeassistant.components.led_infrared.PLATFORMS",
        [Platform.LIGHT],
    ):
        yield


@pytest.mark.parametrize(
    "config_entry",
    [
        LEDIrDeviceType.GENERIC_13_KEY,
        LEDIrDeviceType.GENERIC_24_KEY,
        LEDIrDeviceType.GENERIC_40_KEY,
        LEDIrDeviceType.GENERIC_44_KEY,
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of light platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


# Action, action data and the codes the emitter is expected to send for it.
_LIGHT_ACTIONS: dict[
    LEDIrDeviceType, list[tuple[str, dict[str, str], list[LEDIrKeyCode]]]
] = {
    LEDIrDeviceType.GENERIC_13_KEY: [
        (SERVICE_TURN_ON, {}, [Generic13KeyCode.ON]),
        (SERVICE_TURN_OFF, {}, [Generic13KeyCode.OFF]),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_1"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_1],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_2"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_2],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_3"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_3],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_4"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_4],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_5"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_5],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_6"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_6],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_7"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_7],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_8"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_8],
        ),
    ],
    LEDIrDeviceType.GENERIC_24_KEY: [
        (SERVICE_TURN_ON, {}, [Generic24KeyCode.ON]),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "flash"},
            [Generic24KeyCode.ON, Generic24KeyCode.FLASH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "strobe"},
            [Generic24KeyCode.ON, Generic24KeyCode.STROBE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "fade"},
            [Generic24KeyCode.ON, Generic24KeyCode.FADE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "smooth"},
            [Generic24KeyCode.ON, Generic24KeyCode.SMOOTH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "red"},
            [Generic24KeyCode.ON, Generic24KeyCode.RED],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "green"},
            [Generic24KeyCode.ON, Generic24KeyCode.GREEN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "blue"},
            [Generic24KeyCode.ON, Generic24KeyCode.BLUE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "white"},
            [Generic24KeyCode.ON, Generic24KeyCode.WHITE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "orange_red"},
            [Generic24KeyCode.ON, Generic24KeyCode.ORANGE_RED],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "tomato"},
            [Generic24KeyCode.ON, Generic24KeyCode.TOMATO],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "light_green"},
            [Generic24KeyCode.ON, Generic24KeyCode.LIGHT_GREEN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "sky_blue"},
            [Generic24KeyCode.ON, Generic24KeyCode.SKY_BLUE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "cyan"},
            [Generic24KeyCode.ON, Generic24KeyCode.CYAN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "rebecca_purple"},
            [Generic24KeyCode.ON, Generic24KeyCode.REBECCA_PURPLE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "orange"},
            [Generic24KeyCode.ON, Generic24KeyCode.ORANGE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "turquoise"},
            [Generic24KeyCode.ON, Generic24KeyCode.TURQUOISE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "purple"},
            [Generic24KeyCode.ON, Generic24KeyCode.PURPLE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "yellow"},
            [Generic24KeyCode.ON, Generic24KeyCode.YELLOW],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "dark_cyan"},
            [Generic24KeyCode.ON, Generic24KeyCode.DARK_CYAN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "plum"},
            [Generic24KeyCode.ON, Generic24KeyCode.PLUM],
        ),
        (SERVICE_TURN_OFF, {}, [Generic24KeyCode.OFF]),
    ],
    LEDIrDeviceType.GENERIC_40_KEY: [
        (SERVICE_TURN_ON, {}, [Generic40KeyCode.ON]),
        (SERVICE_TURN_OFF, {}, [Generic40KeyCode.OFF]),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "auto"},
            [Generic40KeyCode.ON, Generic40KeyCode.AUTO],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "fade3"},
            [Generic40KeyCode.ON, Generic40KeyCode.FADE3],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "fade7"},
            [Generic40KeyCode.ON, Generic40KeyCode.FADE7],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "flash"},
            [Generic40KeyCode.ON, Generic40KeyCode.FLASH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "jump3"},
            [Generic40KeyCode.ON, Generic40KeyCode.JUMP3],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "jump7"},
            [Generic40KeyCode.ON, Generic40KeyCode.JUMP7],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "red"},
            [Generic40KeyCode.ON, Generic40KeyCode.RED],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "green"},
            [Generic40KeyCode.ON, Generic40KeyCode.GREEN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "blue"},
            [Generic40KeyCode.ON, Generic40KeyCode.BLUE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "white"},
            [Generic40KeyCode.ON, Generic40KeyCode.WHITE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "tomato"},
            [Generic40KeyCode.ON, Generic40KeyCode.TOMATO],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "light_green"},
            [Generic40KeyCode.ON, Generic40KeyCode.LIGHT_GREEN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "deep_blue"},
            [Generic40KeyCode.ON, Generic40KeyCode.DEEP_BLUE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "floral_white"},
            [Generic40KeyCode.ON, Generic40KeyCode.FLORAL_WHITE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "orange"},
            [Generic40KeyCode.ON, Generic40KeyCode.ORANGE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "turquoise"},
            [Generic40KeyCode.ON, Generic40KeyCode.TURQUOISE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "purple"},
            [Generic40KeyCode.ON, Generic40KeyCode.PURPLE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "lavender_blush"},
            [Generic40KeyCode.ON, Generic40KeyCode.LAVENDER_BLUSH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "yellowish"},
            [Generic40KeyCode.ON, Generic40KeyCode.YELLOWISH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "cyan"},
            [Generic40KeyCode.ON, Generic40KeyCode.CYAN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "magenta"},
            [Generic40KeyCode.ON, Generic40KeyCode.MAGENTA],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "ghost_white"},
            [Generic40KeyCode.ON, Generic40KeyCode.GHOST_WHITE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "yellow"},
            [Generic40KeyCode.ON, Generic40KeyCode.YELLOW],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "aqua"},
            [Generic40KeyCode.ON, Generic40KeyCode.AQUA],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "pink"},
            [Generic40KeyCode.ON, Generic40KeyCode.PINK],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "light_cyan"},
            [Generic40KeyCode.ON, Generic40KeyCode.LIGHT_CYAN],
        ),
    ],
    LEDIrDeviceType.GENERIC_44_KEY: [
        (SERVICE_TURN_ON, {}, [Generic44KeyCode.ON]),
        (SERVICE_TURN_OFF, {}, [Generic44KeyCode.OFF]),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "auto"},
            [Generic44KeyCode.ON, Generic44KeyCode.AUTO],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "fade3"},
            [Generic44KeyCode.ON, Generic44KeyCode.FADE3],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "fade7"},
            [Generic44KeyCode.ON, Generic44KeyCode.FADE7],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "flash"},
            [Generic44KeyCode.ON, Generic44KeyCode.FLASH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "jump3"},
            [Generic44KeyCode.ON, Generic44KeyCode.JUMP3],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "jump7"},
            [Generic44KeyCode.ON, Generic44KeyCode.JUMP7],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "diy1"},
            [Generic44KeyCode.ON, Generic44KeyCode.DIY1],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "diy2"},
            [Generic44KeyCode.ON, Generic44KeyCode.DIY2],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "diy3"},
            [Generic44KeyCode.ON, Generic44KeyCode.DIY3],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "diy4"},
            [Generic44KeyCode.ON, Generic44KeyCode.DIY4],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "diy5"},
            [Generic44KeyCode.ON, Generic44KeyCode.DIY5],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "diy6"},
            [Generic44KeyCode.ON, Generic44KeyCode.DIY6],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "red"},
            [Generic44KeyCode.ON, Generic44KeyCode.RED],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "green"},
            [Generic44KeyCode.ON, Generic44KeyCode.GREEN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "blue"},
            [Generic44KeyCode.ON, Generic44KeyCode.BLUE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "white"},
            [Generic44KeyCode.ON, Generic44KeyCode.WHITE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "tomato"},
            [Generic44KeyCode.ON, Generic44KeyCode.TOMATO],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "light_green"},
            [Generic44KeyCode.ON, Generic44KeyCode.LIGHT_GREEN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "deep_blue"},
            [Generic44KeyCode.ON, Generic44KeyCode.DEEP_BLUE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "floral_white"},
            [Generic44KeyCode.ON, Generic44KeyCode.FLORAL_WHITE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "orange"},
            [Generic44KeyCode.ON, Generic44KeyCode.ORANGE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "turquoise"},
            [Generic44KeyCode.ON, Generic44KeyCode.TURQUOISE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "purple"},
            [Generic44KeyCode.ON, Generic44KeyCode.PURPLE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "lavender_blush"},
            [Generic44KeyCode.ON, Generic44KeyCode.LAVENDER_BLUSH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "yellowish"},
            [Generic44KeyCode.ON, Generic44KeyCode.YELLOWISH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "cyan"},
            [Generic44KeyCode.ON, Generic44KeyCode.CYAN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "magenta"},
            [Generic44KeyCode.ON, Generic44KeyCode.MAGENTA],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "ghost_white"},
            [Generic44KeyCode.ON, Generic44KeyCode.GHOST_WHITE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "yellow"},
            [Generic44KeyCode.ON, Generic44KeyCode.YELLOW],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "aqua"},
            [Generic44KeyCode.ON, Generic44KeyCode.AQUA],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "pink"},
            [Generic44KeyCode.ON, Generic44KeyCode.PINK],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "light_cyan"},
            [Generic44KeyCode.ON, Generic44KeyCode.LIGHT_CYAN],
        ),
    ],
}


@pytest.mark.parametrize("device_type", list(_LIGHT_ACTIONS))
@pytest.mark.usefixtures("infrared_codes")
async def test_light_actions(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    device_type: LEDIrDeviceType,
) -> None:
    """Test light actions."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="LED Infrared via Test IR emitter",
        entry_id="1234567890",
        data={
            CONF_DEVICE_TYPE: device_type,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    for service, service_data, expected_codes in _LIGHT_ACTIONS[device_type]:
        mock_infrared_emitter_entity.send_command_calls.clear()

        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: LIGHT_ENTITY_ID, **service_data},
            blocking=True,
        )

        assert mock_infrared_emitter_entity.send_command_calls == expected_codes
