"""Tests for the device_tracker platform."""

import pytest

from homeassistant.components.weenect.const import ATTRIBUTION, DOMAIN

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("get_trackers")
async def test_device_tracker(hass):
    """Test that device_tracker works."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    entity = hass.states.get("device_tracker.test")
    assert entity.attributes["attribution"] == ATTRIBUTION
    assert entity.attributes["id"] == 100000
    assert entity.attributes["sim"] == "8849390213023093728"
    assert entity.attributes["imei"] == "160389554842512"

    assert entity.state == "not_home"
    assert entity.attributes["source_type"] == "gps"
    assert entity.attributes["latitude"] == 47.024191
    assert entity.attributes["gps_accuracy"] == 31
    assert entity.attributes["icon"] == "mdi:paw"
