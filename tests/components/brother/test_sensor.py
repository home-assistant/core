"""Test sensor of Brother integration."""
from datetime import datetime, timedelta
import json
from unittest.mock import Mock, patch

from homeassistant.components.brother.const import DOMAIN
from homeassistant.components.brother.sensor import UNIT_PAGES
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import UTC, utcnow

from . import init_integration

from tests.common import async_fire_time_changed, load_fixture

ATTR_REMAINING_PAGES = "remaining_pages"
ATTR_COUNTER = "counter"


async def test_sensors(hass: HomeAssistant) -> None:
    """Test states of the sensors."""
    entry = await init_integration(hass, skip_setup=True)

    registry = er.async_get(hass)

    # Pre-create registry entries for disabled by default sensors
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "0123456789_uptime",
        suggested_object_id="hl_l2340dw_last_restart",
        disabled_by=None,
    )
    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=UTC)
    with patch("brother.Brother.initialize"), patch(
        "brother.datetime", now=Mock(return_value=test_time)
    ), patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("printer_data.json", "brother")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.hl_l2340dw_status")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer"
    assert state.state == "waiting"
    assert state.attributes.get(ATTR_STATE_CLASS) is None

    entry = registry.async_get("sensor.hl_l2340dw_status")
    assert entry
    assert entry.unique_id == "0123456789_status"

    state = hass.states.get("sensor.hl_l2340dw_black_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "75"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_black_toner_remaining")
    assert entry
    assert entry.unique_id == "0123456789_black_toner_remaining"

    state = hass.states.get("sensor.hl_l2340dw_cyan_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "10"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_cyan_toner_remaining")
    assert entry
    assert entry.unique_id == "0123456789_cyan_toner_remaining"

    state = hass.states.get("sensor.hl_l2340dw_magenta_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "8"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_magenta_toner_remaining")
    assert entry
    assert entry.unique_id == "0123456789_magenta_toner_remaining"

    state = hass.states.get("sensor.hl_l2340dw_yellow_toner_remaining")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d-nozzle"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "2"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_yellow_toner_remaining")
    assert entry
    assert entry.unique_id == "0123456789_yellow_toner_remaining"

    state = hass.states.get("sensor.hl_l2340dw_drum_remaining_lifetime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_drum_remaining_lifetime")
    assert entry
    assert entry.unique_id == "0123456789_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_drum_remaining_pages")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "11014"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_drum_remaining_pages")
    assert entry
    assert entry.unique_id == "0123456789_drum_remaining_pages"

    state = hass.states.get("sensor.hl_l2340dw_drum_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "986"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_drum_page_counter")
    assert entry
    assert entry.unique_id == "0123456789_drum_counter"

    state = hass.states.get("sensor.hl_l2340dw_black_drum_remaining_lifetime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_black_drum_remaining_lifetime")
    assert entry
    assert entry.unique_id == "0123456789_black_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_black_drum_remaining_pages")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "16389"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_black_drum_remaining_pages")
    assert entry
    assert entry.unique_id == "0123456789_black_drum_remaining_pages"

    state = hass.states.get("sensor.hl_l2340dw_black_drum_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "1611"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_black_drum_page_counter")
    assert entry
    assert entry.unique_id == "0123456789_black_drum_counter"

    state = hass.states.get("sensor.hl_l2340dw_cyan_drum_remaining_lifetime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_cyan_drum_remaining_lifetime")
    assert entry
    assert entry.unique_id == "0123456789_cyan_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_cyan_drum_remaining_pages")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "16389"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_cyan_drum_remaining_pages")
    assert entry
    assert entry.unique_id == "0123456789_cyan_drum_remaining_pages"

    state = hass.states.get("sensor.hl_l2340dw_cyan_drum_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "1611"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_cyan_drum_page_counter")
    assert entry
    assert entry.unique_id == "0123456789_cyan_drum_counter"

    state = hass.states.get("sensor.hl_l2340dw_magenta_drum_remaining_lifetime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_magenta_drum_remaining_lifetime")
    assert entry
    assert entry.unique_id == "0123456789_magenta_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_magenta_drum_remaining_pages")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "16389"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_magenta_drum_remaining_pages")
    assert entry
    assert entry.unique_id == "0123456789_magenta_drum_remaining_pages"

    state = hass.states.get("sensor.hl_l2340dw_magenta_drum_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "1611"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_magenta_drum_page_counter")
    assert entry
    assert entry.unique_id == "0123456789_magenta_drum_counter"

    state = hass.states.get("sensor.hl_l2340dw_yellow_drum_remaining_lifetime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "92"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_yellow_drum_remaining_lifetime")
    assert entry
    assert entry.unique_id == "0123456789_yellow_drum_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_yellow_drum_remaining_pages")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "16389"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_yellow_drum_remaining_pages")
    assert entry
    assert entry.unique_id == "0123456789_yellow_drum_remaining_pages"

    state = hass.states.get("sensor.hl_l2340dw_yellow_drum_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-donut"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "1611"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_yellow_drum_page_counter")
    assert entry
    assert entry.unique_id == "0123456789_yellow_drum_counter"

    state = hass.states.get("sensor.hl_l2340dw_fuser_remaining_lifetime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "97"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_fuser_remaining_lifetime")
    assert entry
    assert entry.unique_id == "0123456789_fuser_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_belt_unit_remaining_lifetime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:current-ac"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "97"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_belt_unit_remaining_lifetime")
    assert entry
    assert entry.unique_id == "0123456789_belt_unit_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_pf_kit_1_remaining_lifetime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer-3d"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "98"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_pf_kit_1_remaining_lifetime")
    assert entry
    assert entry.unique_id == "0123456789_pf_kit_1_remaining_life"

    state = hass.states.get("sensor.hl_l2340dw_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "986"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_page_counter")
    assert entry
    assert entry.unique_id == "0123456789_page_counter"

    state = hass.states.get("sensor.hl_l2340dw_duplex_unit_page_counter")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "538"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_duplex_unit_page_counter")
    assert entry
    assert entry.unique_id == "0123456789_duplex_unit_pages_counter"

    state = hass.states.get("sensor.hl_l2340dw_b_w_pages")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "709"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_b_w_pages")
    assert entry
    assert entry.unique_id == "0123456789_bw_counter"

    state = hass.states.get("sensor.hl_l2340dw_color_pages")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:file-document-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PAGES
    assert state.state == "902"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.hl_l2340dw_color_pages")
    assert entry
    assert entry.unique_id == "0123456789_color_counter"

    state = hass.states.get("sensor.hl_l2340dw_last_restart")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert state.state == "2019-09-24T12:14:56+00:00"
    assert state.attributes.get(ATTR_STATE_CLASS) is None

    entry = registry.async_get("sensor.hl_l2340dw_last_restart")
    assert entry
    assert entry.unique_id == "0123456789_uptime"


async def test_disabled_by_default_sensors(hass: HomeAssistant) -> None:
    """Test the disabled by default Brother sensors."""
    await init_integration(hass)

    registry = er.async_get(hass)
    state = hass.states.get("sensor.hl_l2340dw_last_restart")
    assert state is None

    entry = registry.async_get("sensor.hl_l2340dw_last_restart")
    assert entry
    assert entry.unique_id == "0123456789_uptime"
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when device is offline."""
    await init_integration(hass)

    state = hass.states.get("sensor.hl_l2340dw_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "waiting"

    future = utcnow() + timedelta(minutes=5)
    with patch("brother.Brother.initialize"), patch(
        "brother.Brother._get_data", side_effect=ConnectionError()
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=10)
    with patch("brother.Brother.initialize"), patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("printer_data.json", "brother")),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "waiting"


async def test_manual_update_entity(hass: HomeAssistant) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass)

    data = json.loads(load_fixture("printer_data.json", "brother"))

    await async_setup_component(hass, "homeassistant", {})
    with patch(
        "homeassistant.components.brother.Brother.async_update", return_value=data
    ) as mock_update:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.hl_l2340dw_status"]},
            blocking=True,
        )

        assert len(mock_update.mock_calls) == 1


async def test_unique_id_migration(hass: HomeAssistant) -> None:
    """Test states of the unique_id migration."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "0123456789_b/w_counter",
        suggested_object_id="hl_l2340dw_b_w_counter",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = registry.async_get("sensor.hl_l2340dw_b_w_counter")
    assert entry
    assert entry.unique_id == "0123456789_bw_counter"
