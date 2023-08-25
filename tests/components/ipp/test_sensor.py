"""Tests for the IPP sensor platform."""
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyipp import IPPConnectionError
import pytest

from homeassistant.components.ipp.const import (
    ATTR_MARKER_HIGH_LEVEL,
    ATTR_MARKER_LOW_LEVEL,
    ATTR_MARKER_TYPE,
    DOMAIN,
)
from homeassistant.components.ipp.coordinator import SCAN_INTERVAL
from homeassistant.components.sensor import ATTR_OPTIONS, DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import register_entity

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)


def _mock_restore_cache(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
):
    """Mock entities that would exist in registry after successful printer config entry setup."""
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
    )

    printer_entity_id = register_entity(
        hass,
        entity_registry,
        SENSOR_DOMAIN,
        "test_ha_1000_series",
        "printer",
        entry,
    )

    marker_entity_id = register_entity(
        hass,
        entity_registry,
        SENSOR_DOMAIN,
        "test_ha_1000_series_black_ink",
        "marker_0",
        entry,
    )

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    printer_entity_id,
                    "idle",
                    {
                        ATTR_ICON: "mdi:printer",
                    },
                ),
                {
                    "native_value": "idle",
                    "native_unit_of_measurement": None,
                },
            ),
            (
                State(
                    marker_entity_id,
                    "24",
                    {
                        ATTR_ICON: "mdi:water",
                        ATTR_MARKER_HIGH_LEVEL: 100,
                        ATTR_MARKER_LOW_LEVEL: 10,
                        ATTR_MARKER_TYPE: "ink",
                    },
                ),
                {
                    "native_value": 24,
                    "native_unit_of_measurement": PERCENTAGE,
                },
            ),
        ),
    )

    return (printer_entity_id, marker_entity_id)


@pytest.mark.freeze_time("2019-11-11 09:10:32+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the creation and values of the IPP sensors."""
    state = hass.states.get("sensor.test_ha_1000_series")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_OPTIONS) == ["idle", "printing", "stopped"]

    entry = entity_registry.async_get("sensor.test_ha_1000_series")
    assert entry
    assert entry.translation_key == "printer"

    state = hass.states.get("sensor.test_ha_1000_series_black_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "58"

    state = hass.states.get("sensor.test_ha_1000_series_photo_black_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "98"

    state = hass.states.get("sensor.test_ha_1000_series_cyan_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "91"

    state = hass.states.get("sensor.test_ha_1000_series_yellow_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "95"

    state = hass.states.get("sensor.test_ha_1000_series_magenta_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "73"

    state = hass.states.get("sensor.test_ha_1000_series_uptime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2019-11-11T09:10:02+00:00"

    entry = entity_registry.async_get("sensor.test_ha_1000_series_uptime")
    assert entry
    assert entry.unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251_uptime"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the disabled by default IPP sensors."""
    registry = er.async_get(hass)

    state = hass.states.get("sensor.test_ha_1000_series_uptime")
    assert state is None

    entry = registry.async_get("sensor.test_ha_1000_series_uptime")
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_missing_entry_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp: AsyncMock,
) -> None:
    """Test the unique_id of IPP sensor when printer is missing identifiers."""
    mock_config_entry.unique_id = None
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)

    entity = registry.async_get("sensor.test_ha_1000_series")
    assert entity
    assert entity.unique_id == f"{mock_config_entry.entry_id}_printer"


async def test_restore_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor restore state when device is unavailable."""
    mock_config_entry.add_to_hass(hass)

    (printer_entity_id, marker_entity_id) = _mock_restore_cache(
        hass, device_registry, entity_registry, mock_config_entry
    )

    mock_ipp.printer.side_effect = IPPConnectionError
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    printer_state = hass.states.get(printer_entity_id)
    assert printer_state
    assert printer_state.state == STATE_UNAVAILABLE

    marker_state = hass.states.get(marker_entity_id)
    assert marker_state
    assert marker_state.state == "24"


async def test_restore_sensors_recovered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor restore state when device was unavailable but has since recovered."""
    mock_config_entry.add_to_hass(hass)

    (printer_entity_id, marker_entity_id) = _mock_restore_cache(
        hass, device_registry, entity_registry, mock_config_entry
    )

    mock_ipp.printer.side_effect = IPPConnectionError
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    printer_state = hass.states.get(printer_entity_id)
    assert printer_state
    assert printer_state.state == STATE_UNAVAILABLE

    marker_state = hass.states.get(marker_entity_id)
    assert marker_state
    assert marker_state.state == "24"

    mock_ipp.printer.side_effect = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    printer_state = hass.states.get(printer_entity_id)
    assert printer_state
    assert printer_state.state == "idle"

    marker_state = hass.states.get(marker_entity_id)
    assert marker_state
    assert marker_state.state == "58"
