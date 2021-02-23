"""Test the Litter-Robot sensor entity."""
from unittest.mock import patch

from homeassistant.components import litterrobot
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import PERCENTAGE

from .common import CONFIG

from tests.common import MockConfigEntry

ENTITY_ID = "sensor.test_waste_drawer"


async def setup_hub(hass, mock_hub):
    """Load the Litter-Robot sensor platform with the provided hub."""
    hass.config.components.add(litterrobot.DOMAIN)
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )

    with patch.dict(hass.data, {litterrobot.DOMAIN: {entry.entry_id: mock_hub}}):
        await hass.config_entries.async_forward_entry_setup(entry, PLATFORM_DOMAIN)
        await hass.async_block_till_done()


async def test_sensor(hass, mock_hub):
    """Tests the sensor entity was set up."""
    await setup_hub(hass, mock_hub)

    sensor = hass.states.get(ENTITY_ID)
    assert sensor is not None
    assert sensor.state == "50"
    assert sensor.attributes["cycle_count"] == 15
    assert sensor.attributes["cycle_capacity"] == 30
    assert sensor.attributes["cycles_after_drawer_full"] == 0
    assert sensor.attributes["unit_of_measurement"] == PERCENTAGE
