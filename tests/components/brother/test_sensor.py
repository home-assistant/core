"""Test sensor of Brother integration."""
from datetime import timedelta
import json

from asynctest import patch

from homeassistant.components.brother.const import DOMAIN, UNIT_PAGES
from homeassistant.const import (
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    UNIT_PERCENTAGE,
)
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture

ATTR_REMAINING_PAGES = "remaining_pages"
ATTR_COUNTER = "counter"


async def test_sensors(hass):
    """Test states of the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state
        assert state.attributes.get(ATTR_ICON) == "mdi:printer"
        assert state.state == "waiting"

        state = hass.states.get("sensor.hl_l2340dw_black_toner_remaining")
        assert state
        assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
        assert state.state == "75"

        state = hass.states.get("sensor.hl_l2340dw_black_drum_remaining_life")
        assert state
        assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
        assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
        assert state.attributes.get(ATTR_COUNTER) == 1611
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
        assert state.state == "92"

        state = hass.states.get("sensor.hl_l2340dw_page_counter")
        assert state
        assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
        assert state.state == "986"


async def test_availability(hass):
    """Ensure that we mark the entities unavailable correctly when device is offline."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "waiting"

    future = utcnow() + timedelta(minutes=5)
    with patch("brother.Brother._get_data", side_effect=ConnectionError()):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=10)
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "waiting"
