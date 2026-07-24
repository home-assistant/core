"""Tests for the LED Infrared button platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.led import Generic13KeyCode, Generic24KeyCode
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
    ],
)
@pytest.mark.usefixtures("infrared_codes")
async def test_button_press(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    device_type: LEDIrDeviceType,
    key: str,
    expected_codes: list[Generic24KeyCode | Generic13KeyCode],
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

    entity_id = er.async_get(hass).async_get_entity_id(
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
