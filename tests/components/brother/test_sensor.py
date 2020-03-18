"""Test sensor of Brother integration."""
from datetime import timedelta
import json

from asynctest import patch

from homeassistant.components.brother.const import UNIT_PAGES
from homeassistant.const import (
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    TIME_DAYS,
    UNIT_PERCENTAGE,
)
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed, load_fixture
from tests.components.brother import init_integration

ATTR_REMAINING_PAGES = "remaining_pages"
ATTR_COUNTER = "counter"


async def test_sensors(hass):
    """Test states of the sensors."""
    await init_integration(hass)

    state = hass.states.get("sensor.hl_l2340dw_status")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer"
    assert state.state == "waiting"

    state = hass.states.get("sensor.hl_l2340dw_black_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "75"

    state = hass.states.get("sensor.hl_l2340dw_cyan_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "10"

    state = hass.states.get("sensor.hl_l2340dw_magenta_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "8"

    state = hass.states.get("sensor.hl_l2340dw_yellow_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "2"

    state = hass.states.get("sensor.hl_l2340dw_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 11014
    assert state.attributes.get(ATTR_COUNTER) == 986
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "92"

    state = hass.states.get("sensor.hl_l2340dw_black_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
    assert state.attributes.get(ATTR_COUNTER) == 1611
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "92"

    state = hass.states.get("sensor.hl_l2340dw_cyan_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
    assert state.attributes.get(ATTR_COUNTER) == 1611
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "92"

    state = hass.states.get("sensor.hl_l2340dw_magenta_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
    assert state.attributes.get(ATTR_COUNTER) == 1611
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "92"

    state = hass.states.get("sensor.hl_l2340dw_yellow_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
    assert state.attributes.get(ATTR_COUNTER) == 1611
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "92"

    state = hass.states.get("sensor.hl_l2340dw_fuser_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "97"

    state = hass.states.get("sensor.hl_l2340dw_belt_unit_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:current-ac"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "97"

    state = hass.states.get("sensor.hl_l2340dw_pf_kit_1_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.state == "98"

    state = hass.states.get("sensor.hl_l2340dw_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "986"

    state = hass.states.get("sensor.hl_l2340dw_duplex_unit_pages_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "538"

    state = hass.states.get("sensor.hl_l2340dw_b_w_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "709"

    state = hass.states.get("sensor.hl_l2340dw_color_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "902"

    state = hass.states.get("sensor.hl_l2340dw_uptime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TIME_DAYS
    assert state.state == "48"


async def test_availability(hass):
    """Ensure that we mark the entities unavailable correctly when device is offline."""
    await init_integration(hass)

    state = hass.states.get("sensor.hl_l2340dw_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "waiting"

    future = utcnow() + timedelta(minutes=5)
    with patch("brother.Brother._get_data", side_effect=ConnectionError()):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=10)
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "waiting"
