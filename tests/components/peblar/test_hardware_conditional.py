"""Tests for hardware-conditional Peblar select entities."""

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "init_integration_without_buzzer", [Platform.SELECT], indirect=True
)
@pytest.mark.usefixtures("init_integration_without_buzzer")
async def test_buzzer_volume_absent_without_buzzer(
    hass: HomeAssistant,
) -> None:
    """Test buzzer volume select absent when HwHasBuzzer=false."""
    assert hass.states.get("select.peblar_ev_charger_buzzer_volume") is None


@pytest.mark.parametrize(
    "init_integration_without_led", [Platform.SELECT], indirect=True
)
@pytest.mark.usefixtures("init_integration_without_led")
async def test_led_brightness_absent_without_led(
    hass: HomeAssistant,
) -> None:
    """Test LED brightness select absent when HwHasLed=false."""
    assert hass.states.get("select.peblar_ev_charger_led_brightness") is None
