"""Test pi_hole sensor."""

from homeassistant.components.pi_hole import (
    sensor as pi_hole,
    DOMAIN as PIHOLE_DOMAIN,
    PiHoleData,
)


added_sensors = []


def mock_async_add_entities(sensors, enable):
    """Mock function."""
    global added_sensors
    added_sensors = sensors
    return


async def test_setup_no_monitored_conditions(hass):
    """Test a successful setup with no monitored_conditions."""
    hass.data[PIHOLE_DOMAIN] = PiHoleData(None, None)

    config = {}
    await pi_hole.async_setup_platform(hass, config, mock_async_add_entities, None)

    assert len(added_sensors) == 0
