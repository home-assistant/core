"""Tests for the LED Infrared light platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.tween_light.led_strip import TweenLightLEDStripCode
import pytest
from syrupy.assertion import SnapshotAssertion

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
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture(autouse=True)
def light_only() -> Generator[None]:
    """Enable only the light platform."""
    with patch(
        "homeassistant.components.led_infrared.PLATFORMS",
        [Platform.LIGHT],
    ):
        yield


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
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
    ("service", "service_data", "expected_codes"),
    [
        (SERVICE_TURN_ON, {}, [TweenLightLEDStripCode.ON]),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "flash"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.FLASH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "strobe"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.STROBE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "fade"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.FADE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "smooth"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.SMOOTH],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "red"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.RED],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "green"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.GREEN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "blue"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.BLUE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "white"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.WHITE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "orange_red"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.ORANGE_RED],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "tomato"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.TOMATO],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "light_green"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.LIGHT_GREEN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "sky_blue"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.SKY_BLUE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "cyan"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.CYAN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "rebecca_purple"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.REBECCA_PURPLE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "orange"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.ORANGE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "turquoise"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.TURQUOISE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "purple"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.PURPLE],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "yellow"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.YELLOW],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "dark_cyan"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.DARK_CYAN],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "plum"},
            [TweenLightLEDStripCode.ON, TweenLightLEDStripCode.PLUM],
        ),
        (SERVICE_TURN_OFF, {}, [TweenLightLEDStripCode.OFF]),
    ],
)
@pytest.mark.usefixtures("mock_infrared_receiver_entity", "led_strip_codes")
async def test_light_actions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    service_data: dict[str, str],
    expected_codes: list[TweenLightLEDStripCode],
) -> None:
    """Test light actions."""

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
