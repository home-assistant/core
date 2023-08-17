"""The sensor tests for the IPMA platform."""

from unittest.mock import patch

from . import ENTRY_CONFIG, MockLocation

from tests.common import MockConfigEntry


async def test_ipma_fire_risk_create_sensors(hass):
    """Test creation of fire risk sensors."""

    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=ENTRY_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.home_town_fire_risk")

    assert state.state == "3"
