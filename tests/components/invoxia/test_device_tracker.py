"""Test the Invoxia (unofficial) device_tracker platform."""
from unittest.mock import patch
import uuid

import gps_tracker

from homeassistant.components.device_tracker.const import ATTR_SOURCE_TYPE
from homeassistant.components.invoxia.const import DOMAIN
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_ENTITIES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity

from .const import TEST_CONF

from tests.common import MockConfigEntry


async def test_device_tracker_add_entities(
    hass: HomeAssistant, trackers, tracker_status, tracker_data
) -> None:
    """Test for device_tracker registration."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_CONF, unique_id=uuid.uuid4().hex
    )
    mock_config_entry.add_to_hass(hass)
    entry_id = mock_config_entry.entry_id

    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_devices",
        return_value=[],
    ), patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        return_value=trackers,
    ), patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_tracker_status",
        return_value=tracker_status,
    ), patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_locations",
        return_value=tracker_data,
    ):
        await hass.config_entries.async_setup(entry_id)
        await hass.async_block_till_done()

    # Test entry properties
    entity_registry = er.async_get(hass)
    entry: er.RegistryEntry = entity_registry.async_get("device_tracker.dummy_tracker")
    assert entry
    assert entry.unique_id == "999999"

    # Test state
    state = hass.states.get("device_tracker.dummy_tracker")
    assert state
    assert state.attributes.get(ATTR_SOURCE_TYPE) == "gps"
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == tracker_status.battery
    assert state.attributes.get(ATTR_GPS_ACCURACY) == tracker_data[0].precision
    assert state.attributes.get(ATTR_LATITUDE) == tracker_data[0].lat
    assert state.attributes.get(ATTR_LONGITUDE) == tracker_data[0].lng

    # Test connection failure
    entity: Entity = hass.data[DOMAIN][entry_id][CONF_ENTITIES][0]
    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_tracker_status",
        side_effect=gps_tracker.client.exceptions.ApiConnectionError(),
    ), patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_locations",
        return_value=tracker_data,
    ):
        await entity.coordinator.async_refresh()
        await hass.async_block_till_done()

    assert not entity.available

    # Test connection back to working
    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_tracker_status",
        return_value=tracker_status,
    ), patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_locations",
        return_value=tracker_data,
    ):
        await entity.async_update_ha_state(True)
        await hass.async_block_till_done()

    assert entity.available

    # Test disabling and updating device
    entity_registry.async_update_entity(
        "device_tracker.dummy_tracker", disabled_by=er.RegistryEntryDisabler.HASS
    )
    updated_registry_entry: er.RegistryEntry = entity_registry.async_get(
        "device_tracker.dummy_tracker"
    )

    entity.registry_entry = updated_registry_entry
    assert not entity.enabled
    await entity.async_update_ha_state(True)
    await hass.async_block_till_done()

    # Unload the ConfigEntry
    assert len(hass.data[DOMAIN]) == 1
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert len(hass.data[DOMAIN]) == 0
