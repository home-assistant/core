"""The test for the Coolmaster binary sensor platform."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


async def test_clean_filter(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster clean filter binary sensor."""
    assert hass.states.get("binary_sensor.l1_100_clean_filter").state == STATE_OFF
    assert hass.states.get("binary_sensor.l1_101_clean_filter").state == STATE_ON


async def test_demand(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster demand binary sensor."""
    assert hass.states.get("binary_sensor.l1_100_demand").state == STATE_OFF
    assert hass.states.get("binary_sensor.l1_101_demand").state == STATE_ON
    assert hass.states.get("binary_sensor.l1_102_demand").state == STATE_OFF
    assert hass.states.get("binary_sensor.l1_103_demand").state == STATE_ON
    # The legacy status format does not report demand at all.
    assert hass.states.get("binary_sensor.l1_104_demand").state == STATE_UNKNOWN
