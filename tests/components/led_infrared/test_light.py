"""Tests for the LED Infrared light platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.led import Generic13KeyCode, Generic24KeyCode
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


@pytest.mark.parametrize(
    ("device_type", "service", "service_data", "expected_codes"),
    [
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {},
            [Generic24KeyCode.ON],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "flash"},
            [Generic24KeyCode.ON, Generic24KeyCode.FLASH],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "strobe"},
            [Generic24KeyCode.ON, Generic24KeyCode.STROBE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "fade"},
            [Generic24KeyCode.ON, Generic24KeyCode.FADE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "smooth"},
            [Generic24KeyCode.ON, Generic24KeyCode.SMOOTH],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "red"},
            [Generic24KeyCode.ON, Generic24KeyCode.RED],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "green"},
            [Generic24KeyCode.ON, Generic24KeyCode.GREEN],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "blue"},
            [Generic24KeyCode.ON, Generic24KeyCode.BLUE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "white"},
            [Generic24KeyCode.ON, Generic24KeyCode.WHITE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "orange_red"},
            [Generic24KeyCode.ON, Generic24KeyCode.ORANGE_RED],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "tomato"},
            [Generic24KeyCode.ON, Generic24KeyCode.TOMATO],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "light_green"},
            [Generic24KeyCode.ON, Generic24KeyCode.LIGHT_GREEN],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "sky_blue"},
            [Generic24KeyCode.ON, Generic24KeyCode.SKY_BLUE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "cyan"},
            [Generic24KeyCode.ON, Generic24KeyCode.CYAN],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "rebecca_purple"},
            [Generic24KeyCode.ON, Generic24KeyCode.REBECCA_PURPLE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "orange"},
            [Generic24KeyCode.ON, Generic24KeyCode.ORANGE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "turquoise"},
            [Generic24KeyCode.ON, Generic24KeyCode.TURQUOISE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "purple"},
            [Generic24KeyCode.ON, Generic24KeyCode.PURPLE],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "yellow"},
            [Generic24KeyCode.ON, Generic24KeyCode.YELLOW],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "dark_cyan"},
            [Generic24KeyCode.ON, Generic24KeyCode.DARK_CYAN],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "plum"},
            [Generic24KeyCode.ON, Generic24KeyCode.PLUM],
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            SERVICE_TURN_OFF,
            {},
            [Generic24KeyCode.OFF],
        ),
        (LEDIrDeviceType.GENERIC_13_KEY, SERVICE_TURN_ON, {}, [Generic13KeyCode.ON]),
        (LEDIrDeviceType.GENERIC_13_KEY, SERVICE_TURN_OFF, {}, [Generic13KeyCode.OFF]),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_1"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_1],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_2"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_2],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_3"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_3],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_4"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_4],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_5"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_5],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_6"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_6],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_7"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_7],
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "mode_8"},
            [Generic13KeyCode.ON, Generic13KeyCode.MODE_8],
        ),
    ],
)
@pytest.mark.usefixtures("infrared_codes")
async def test_light_actions(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    device_type: LEDIrDeviceType,
    service: str,
    service_data: dict[str, str],
    expected_codes: list[Generic24KeyCode | Generic13KeyCode],
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

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "light.led_infrared_via_test_ir_emitter", **service_data},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == len(expected_codes)
    assert mock_infrared_emitter_entity.send_command_calls == expected_codes
