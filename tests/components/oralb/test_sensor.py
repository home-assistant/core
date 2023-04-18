"""Test the OralB sensors."""

from homeassistant.components.oralb.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant

from . import (
    ORALB_IO_SERIES_4_SERVICE_INFO,
    ORALB_IO_SERIES_6_SERVICE_INFO,
    ORALB_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    inject_bluetooth_service_info_bleak,
)


async def test_sensors(
    hass: HomeAssistant, entity_registry_enabled_by_default: None
) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ORALB_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, ORALB_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 9

    toothbrush_sensor = hass.states.get(
        "sensor.smart_series_7000_48be_toothbrush_state"
    )
    toothbrush_sensor_attrs = toothbrush_sensor.attributes
    assert toothbrush_sensor.state == "running"
    assert (
        toothbrush_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Smart Series 7000 48BE Toothbrush State"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_io_series_4(
    hass: HomeAssistant, entity_registry_enabled_by_default: None
) -> None:
    """Test setting up creates the sensors with an io series 4."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ORALB_IO_SERIES_4_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, ORALB_IO_SERIES_4_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 9

    toothbrush_sensor = hass.states.get("sensor.io_series_4_48be_mode")
    toothbrush_sensor_attrs = toothbrush_sensor.attributes
    assert toothbrush_sensor.state == "gum care"
    assert toothbrush_sensor_attrs[ATTR_FRIENDLY_NAME] == "IO Series 4 48BE Mode"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_battery(hass: HomeAssistant) -> None:
    """Test receiving battery percentage."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ORALB_IO_SERIES_6_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(hass, ORALB_IO_SERIES_6_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 7

    bat_sensor = hass.states.get("sensor.io_series_6_7_1dcf_battery")
    assert bat_sensor.state == "49"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
