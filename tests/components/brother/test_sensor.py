"""Test sensor of Brother integration."""
from datetime import datetime, timedelta
import json

from homeassistant.components.brother.const import DOMAIN, UNIT_PAGES
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import UTC, utcnow

from tests.async_mock import Mock, patch
from tests.common import async_fire_time_changed, load_fixture
from tests.components.brother import init_integration

ATTR_REMAINING_PAGES = "remaining_pages"
ATTR_COUNTER = "counter"


async def test_sensors(hass):
    """Test states of the sensors."""
    entry = await init_integration(hass, skip_setup=True)

    registry = await hass.helpers.entity_registry.async_get_registry()

    # Pre-create registry entries for disabled by default sensors
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "0123456789_uptime",
        suggested_object_id="hl_l2340dw_uptime",
        disabled_by=None,
    )
    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=UTC)
    with patch("brother.datetime", utcnow=Mock(return_value=test_time)), patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.hl_l2340dw_status")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer"
    assert state.state == "waiting"

    entry = registry.async_get("sensor.hl_l2340dw_status")
    assert entry
    assert entry.unique_id == "0123456789_status"

    state = hass.states.get("sensor.hl_l2340dw_black_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "75"

    entry = registry.async_get("sensor.hl_l2340dw_black_toner_remaining")
    assert entry
    assert entry.unique_id == "0123456789_black_toner_remaining"

    state = hass.states.get("sensor.hl_l2340dw_cyan_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "10"

    entry = registry.async_get("sensor.hl_l2340dw_cyan_toner_remaining")
    assert entry
    assert entry.unique_id == "0123456789_cyan_toner_remaining"

    state = hass.states.get("sensor.hl_l2340dw_magenta_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "8"

    entry = registry.async_get("sensor.hl_l2340dw_magenta_toner_remaining")
    assert entry
    assert entry.unique_id == "0123456789_magenta_toner_remaining"

    state = hass.states.get("sensor.hl_l2340dw_yellow_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "2"

    entry = registry.async_get("sensor.hl_l2340dw_yellow_toner_remaining")
    assert entry
    assert entry.unique_id == "0123456789_yellow_toner_remaining"

    state = hass.states.get("sensor.hl_l2340dw_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 11014
    assert state.attributes.get(ATTR_COUNTER) == 986
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"

    entry = registry.async_get("sensor.hl_l2340dw_drum_remaining_life")
    assert entry
    assert entry.unique_id == "0123456789_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_black_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
    assert state.attributes.get(ATTR_COUNTER) == 1611
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"

    entry = registry.async_get("sensor.hl_l2340dw_black_drum_remaining_life")
    assert entry
    assert entry.unique_id == "0123456789_black_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_cyan_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
    assert state.attributes.get(ATTR_COUNTER) == 1611
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"

    entry = registry.async_get("sensor.hl_l2340dw_cyan_drum_remaining_life")
    assert entry
    assert entry.unique_id == "0123456789_cyan_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_magenta_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
    assert state.attributes.get(ATTR_COUNTER) == 1611
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"

    entry = registry.async_get("sensor.hl_l2340dw_magenta_drum_remaining_life")
    assert entry
    assert entry.unique_id == "0123456789_magenta_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_yellow_drum_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_REMAINING_PAGES) == 16389
    assert state.attributes.get(ATTR_COUNTER) == 1611
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"

    entry = registry.async_get("sensor.hl_l2340dw_yellow_drum_remaining_life")
    assert entry
    assert entry.unique_id == "0123456789_yellow_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_fuser_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "97"

    entry = registry.async_get("sensor.hl_l2340dw_fuser_remaining_life")
    assert entry
    assert entry.unique_id == "0123456789_fuser_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_belt_unit_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:current-ac"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "97"

    entry = registry.async_get("sensor.hl_l2340dw_belt_unit_remaining_life")
    assert entry
    assert entry.unique_id == "0123456789_belt_unit_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_pf_kit_1_remaining_life")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "98"

    entry = registry.async_get("sensor.hl_l2340dw_pf_kit_1_remaining_life")
    assert entry
    assert entry.unique_id == "0123456789_pf_kit_1_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "986"

    entry = registry.async_get("sensor.hl_l2340dw_page_counter")
    assert entry
    assert entry.unique_id == "0123456789_page_counter"

    state = hass.states.get("sensor.hl_l2340dw_duplex_unit_pages_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "538"

    entry = registry.async_get("sensor.hl_l2340dw_duplex_unit_pages_counter")
    assert entry
    assert entry.unique_id == "0123456789_duplex_unit_pages_counter"

    state = hass.states.get("sensor.hl_l2340dw_b_w_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "709"

    entry = registry.async_get("sensor.hl_l2340dw_b_w_counter")
    assert entry
    assert entry.unique_id == "0123456789_b/w_counter"

    state = hass.states.get("sensor.hl_l2340dw_color_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "902"

    entry = registry.async_get("sensor.hl_l2340dw_color_counter")
    assert entry
    assert entry.unique_id == "0123456789_color_counter"

    state = hass.states.get("sensor.hl_l2340dw_uptime")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TIMESTAMP
    assert state.state == "2019-09-24T12:14:56+00:00"

    entry = registry.async_get("sensor.hl_l2340dw_uptime")
    assert entry
    assert entry.unique_id == "0123456789_uptime"


async def test_disabled_by_default_sensors(hass):
    """Test the disabled by default Brother sensors."""
    await init_integration(hass)

    registry = await hass.helpers.entity_registry.async_get_registry()
    state = hass.states.get("sensor.hl_l2340dw_uptime")
    assert state is None

    entry = registry.async_get("sensor.hl_l2340dw_uptime")
    assert entry
    assert entry.unique_id == "0123456789_uptime"
    assert entry.disabled
    assert entry.disabled_by == "integration"


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


async def test_manual_update_entity(hass):
    """Test manual update entity via service homeasasistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})
    with patch("homeassistant.components.brother.Brother.async_update") as mock_update:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.hl_l2340dw_status"]},
            blocking=True,
        )

        assert len(mock_update.mock_calls) == 1
