"""Tests for the LED Infrared button platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.led import (
    BaseGenericLEDCode,
    Generic10KeyCode,
    Generic13KeyCode,
    Generic24KeyCode,
    Generic40KeyCode,
    Generic44KeyCode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.led_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    LEDIrDeviceType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture(autouse=True)
def button_only() -> Generator[None]:
    """Enable only the button platform."""
    with patch(
        "homeassistant.components.led_infrared.PLATFORMS",
        [Platform.BUTTON],
    ):
        yield


@pytest.mark.parametrize(
    "config_entry",
    [
        LEDIrDeviceType.GENERIC_10_KEY,
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
    """Snapshot test states of button platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_type", "key", "expected_codes"),
    [
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            "brightness_up",
            [Generic24KeyCode.BRIGHTNESS_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            "brightness_down",
            [Generic24KeyCode.BRIGHTNESS_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            "brightness_up",
            [Generic13KeyCode.BRIGHTNESS_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            "brightness_down",
            [Generic13KeyCode.BRIGHTNESS_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            "timer",
            [Generic13KeyCode.TIMER],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "brightness_up",
            [Generic40KeyCode.BRIGHTNESS_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "brightness_down",
            [Generic40KeyCode.BRIGHTNESS_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "white_brightness_up",
            [Generic40KeyCode.WHITE_BRIGHTNESS_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "white_brightness_down",
            [Generic40KeyCode.WHITE_BRIGHTNESS_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "white_on",
            [Generic40KeyCode.WHITE_ON],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "white_off",
            [Generic40KeyCode.WHITE_OFF],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "white_brightness_25",
            [Generic40KeyCode.WHITE_BRIGHTNESS_25],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "white_brightness_50",
            [Generic40KeyCode.WHITE_BRIGHTNESS_50],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "white_brightness_75",
            [Generic40KeyCode.WHITE_BRIGHTNESS_75],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "white_brightness_100",
            [Generic40KeyCode.WHITE_BRIGHTNESS_100],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "quick",
            [Generic40KeyCode.QUICK],
        ),
        (
            LEDIrDeviceType.GENERIC_40_KEY,
            "slow",
            [Generic40KeyCode.SLOW],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "brightness_up",
            [Generic44KeyCode.BRIGHTNESS_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "brightness_down",
            [Generic44KeyCode.BRIGHTNESS_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "red_up",
            [Generic44KeyCode.RED_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "green_up",
            [Generic44KeyCode.GREEN_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "blue_up",
            [Generic44KeyCode.BLUE_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "red_down",
            [Generic44KeyCode.RED_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "green_down",
            [Generic44KeyCode.GREEN_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "blue_down",
            [Generic44KeyCode.BLUE_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "quick",
            [Generic44KeyCode.QUICK],
        ),
        (
            LEDIrDeviceType.GENERIC_44_KEY,
            "slow",
            [Generic44KeyCode.SLOW],
        ),
        (
            LEDIrDeviceType.GENERIC_10_KEY,
            "brightness_up",
            [Generic10KeyCode.BRIGHTNESS_UP],
        ),
        (
            LEDIrDeviceType.GENERIC_10_KEY,
            "brightness_down",
            [Generic10KeyCode.BRIGHTNESS_DOWN],
        ),
        (
            LEDIrDeviceType.GENERIC_10_KEY,
            "timer_2h",
            [Generic10KeyCode.TIMER_2H],
        ),
        (
            LEDIrDeviceType.GENERIC_10_KEY,
            "timer_4h",
            [Generic10KeyCode.TIMER_4H],
        ),
        (
            LEDIrDeviceType.GENERIC_10_KEY,
            "timer_6h",
            [Generic10KeyCode.TIMER_6H],
        ),
        (
            LEDIrDeviceType.GENERIC_10_KEY,
            "timer_8h",
            [Generic10KeyCode.TIMER_8H],
        ),
    ],
)
@pytest.mark.usefixtures("infrared_codes")
async def test_button_press(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
    device_type: LEDIrDeviceType,
    key: str,
    expected_codes: list[BaseGenericLEDCode],
) -> None:
    """Test button press action."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="LED Infrared",
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

    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{config_entry.entry_id}_{key}"
    )
    assert entity_id is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == len(expected_codes)
    assert mock_infrared_emitter_entity.send_command_calls == expected_codes
