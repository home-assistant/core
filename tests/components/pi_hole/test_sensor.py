"""Test pi_hole sensor."""

from homeassistant.components.pi_hole import (
    sensor as pi_hole,
    DOMAIN as PIHOLE_DOMAIN,
    PiHoleData,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS


added_sensors = []


def mock_async_add_entities(sensors, enable):
    """Mock function."""
    global added_sensors
    added_sensors = sensors
    return


async def test_setup_no_monitored_conditions(hass):
    """Test a successful setup with no monitored_conditions."""
    hass.data[PIHOLE_DOMAIN] = PiHoleData(None, None)

    config = {CONF_MONITORED_CONDITIONS: []}
    await pi_hole.async_setup_platform(hass, config, mock_async_add_entities, None)

    assert len(added_sensors) == 0


async def test_setup_monitored_conditions(hass):
    """Test a successful setup with no monitored_conditions."""
    hass.data[PIHOLE_DOMAIN] = PiHoleData(None, "Unit Test")

    config = {CONF_MONITORED_CONDITIONS: ["ads_blocked_today"]}
    await pi_hole.async_setup_platform(hass, config, mock_async_add_entities, None)

    assert len(added_sensors) == 1
    assert added_sensors[0].name == "Unit Test Ads Blocked Today"
