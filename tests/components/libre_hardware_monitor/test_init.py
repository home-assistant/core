"""Tests for the LibreHardwareMonitor init."""

import logging
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.libre_hardware_monitor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .conftest import VALID_CONFIG

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.mark.usefixtures("mock_lhm_client")
async def test_unique_id_migration(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of entities with old unique ID format."""
    # Create a new config entry with version 1 to trigger migration
    config_entry_v1 = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.20:8085",
        data=VALID_CONFIG,
        entry_id="test_entry_id",
        version=1,
    )

    # Add the config entry to Home Assistant
    config_entry_v1.add_to_hass(hass)

    # Use an actual sensor ID from the mock data (without leading slash)
    actual_sensor_id = "lpc-nct6687d-0-voltage-0"

    # Manually create entity with old unique ID format first
    old_unique_id = f"lhm-{actual_sensor_id}"
    entity_id = "sensor.msi_mag_b650m_mortar_wifi_ms_7d76_12v_voltage"

    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id="msi_mag_b650m_mortar_wifi_ms_7d76_12v_voltage",
        config_entry=config_entry_v1,
    )

    # Verify entity exists with old unique ID
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id)
        == entity_id
    )

    # Ensure entity registry is synchronized before migration
    await hass.async_block_till_done()

    # Verify the entity is actually in the registry before migration
    entity_registry_after = er.async_get(hass)
    assert (
        entity_registry_after.async_get_entity_id("sensor", DOMAIN, old_unique_id)
        == entity_id
    )

    # Now initialize the integration - this should trigger the migration
    await init_integration(hass, config_entry_v1)

    # Wait for the integration to fully load
    await hass.async_block_till_done()

    # Get the entity from registry to verify the migration
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None, "Entity should exist after migration"

    # Verify that the unique ID has been updated
    new_unique_id = f"{config_entry_v1.entry_id}_{actual_sensor_id}"
    assert entity_entry.unique_id == new_unique_id, (
        f"Unique ID not migrated: {entity_entry.unique_id}"
    )

    # Double check that looking up by old ID returns None
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None
