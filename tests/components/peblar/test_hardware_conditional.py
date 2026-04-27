"""Tests for hardware-conditional Peblar select entities."""

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    "init_integration_without_buzzer", [Platform.SELECT], indirect=True
)
@pytest.mark.usefixtures("init_integration_without_buzzer")
async def test_buzzer_volume_absent_without_buzzer(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test buzzer volume select absent when HwHasBuzzer=false."""
    entity_id = "select.peblar_ev_charger_buzzer_volume"
    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize(
    "init_integration_without_led", [Platform.SELECT], indirect=True
)
@pytest.mark.usefixtures("init_integration_without_led")
async def test_led_brightness_absent_without_led(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test LED brightness select absent when HwHasLed=false."""
    entity_id = "select.peblar_ev_charger_led_brightness"
    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get(entity_id) is None
