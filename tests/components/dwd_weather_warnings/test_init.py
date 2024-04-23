"""Tests for Deutscher Wetterdienst (DWD) Weather Warnings integration."""

from typing import Final

from homeassistant.components.dwd_weather_warnings.const import (
    ADVANCE_WARNING_SENSOR,
    CONF_REGION_DEVICE_TRACKER,
    CONF_REGION_IDENTIFIER,
    CURRENT_WARNING_SENSOR,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    STATE_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

DEMO_IDENTIFIER_CONFIG_ENTRY: Final = {
    CONF_NAME: "Unit Test",
    CONF_REGION_IDENTIFIER: "807111000",
    CONF_MONITORED_CONDITIONS: [CURRENT_WARNING_SENSOR, ADVANCE_WARNING_SENSOR],
}

DEMO_TRACKER_CONFIG_ENTRY: Final = {
    CONF_NAME: "Unit Test",
    CONF_REGION_DEVICE_TRACKER: "device_tracker.test_gps",
    CONF_MONITORED_CONDITIONS: [CURRENT_WARNING_SENSOR, ADVANCE_WARNING_SENSOR],
}


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Test loading and unloading the integration with a region identifier based entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=DEMO_IDENTIFIER_CONFIG_ENTRY)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_load_invalid_registry_entry(hass: HomeAssistant) -> None:
    """Test loading the integration with an invalid registry entry ID."""
    INVALID_DATA = DEMO_TRACKER_CONFIG_ENTRY.copy()
    INVALID_DATA[CONF_REGION_DEVICE_TRACKER] = "invalid_registry_id"
    entry = MockConfigEntry(domain=DOMAIN, data=INVALID_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_load_missing_device_tracker(hass: HomeAssistant) -> None:
    """Test loading the integration with a missing device tracker."""
    entry = MockConfigEntry(domain=DOMAIN, data=DEMO_TRACKER_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_load_missing_required_attribute(hass: HomeAssistant) -> None:
    """Test loading the integration with a device tracker missing a required attribute."""
    entry = MockConfigEntry(domain=DOMAIN, data=DEMO_TRACKER_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    hass.states.async_set(
        DEMO_TRACKER_CONFIG_ENTRY[CONF_REGION_DEVICE_TRACKER],
        STATE_HOME,
        {ATTR_LONGITUDE: "7.610263"},
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_load_valid_device_tracker(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test loading the integration with a valid device tracker based entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=DEMO_TRACKER_CONFIG_ENTRY)
    entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "device_tracker",
        entry.domain,
        "uuid",
        suggested_object_id="test_gps",
        config_entry=entry,
    )

    hass.states.async_set(
        DEMO_TRACKER_CONFIG_ENTRY[CONF_REGION_DEVICE_TRACKER],
        STATE_HOME,
        {ATTR_LATITUDE: "50.180454", ATTR_LONGITUDE: "7.610263"},
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]
