"""Tests for hardware-conditional Peblar select entities."""

import pytest

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "mock_peblar", ["system_information_no_buzzer.json"], indirect=True
)
@pytest.mark.parametrize("init_integration", [Platform.SELECT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_buzzer_volume_absent_without_buzzer(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test buzzer volume select absent when HwHasBuzzer=false."""
    assert (
        entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{mock_config_entry.unique_id}_buzzer_volume"
        )
        is None
    )


@pytest.mark.parametrize(
    "mock_peblar", ["system_information_no_led.json"], indirect=True
)
@pytest.mark.parametrize("init_integration", [Platform.SELECT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_led_brightness_absent_without_led(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test LED brightness select absent when HwHasLed=false."""
    assert (
        entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{mock_config_entry.unique_id}_led_brightness"
        )
        is None
    )
