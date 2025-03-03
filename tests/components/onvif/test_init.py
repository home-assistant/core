"""Tests for the ONVIF integration __init__ module."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.onvif import _migrate_camera_entities_unique_ids
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_migrate_camera_entities_unique_ids(hass: HomeAssistant) -> None:
    """Test that camera entities unique ids get migrated properly."""

    config_entry = MockConfigEntry(domain="onvif")
    config_entry.add_to_hass(hass)

    device = MagicMock()
    device.info.mac = "aa:bb:cc:dd:ee:ff"
    device.info.serial_number = None
    device.profiles = [
        MagicMock(token="profile_token_0"),
        MagicMock(token="profile_token_1"),
        MagicMock(token="profile_token_2"),
    ]

    entity_registry = er.async_get(hass)

    entity_with_only_mac = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id="aa:bb:cc:dd:ee:ff",
        config_entry=config_entry,
    )
    entity_with_index = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id="aa:bb:cc:dd:ee:ff_1",
        config_entry=config_entry,
    )
    # This one should not be migrated (different domain)
    entity_sensor = entity_registry.async_get_or_create(
        domain="sensor",
        platform="onvif",
        unique_id="aa:bb:cc:dd:ee:ff",
        config_entry=config_entry,
    )
    # This one should not be migrated (already migrated)
    entity_migrated = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id="aa:bb:cc:dd:ee:ff#profile_token_2",
        config_entry=config_entry,
    )

    _migrate_camera_entities_unique_ids(hass, config_entry, device)

    entity_with_only_mac = entity_registry.async_get(entity_with_only_mac.entity_id)
    entity_with_index = entity_registry.async_get(entity_with_index.entity_id)
    entity_sensor = entity_registry.async_get(entity_sensor.entity_id)
    entity_migrated = entity_registry.async_get(entity_migrated.entity_id)

    assert entity_with_only_mac is not None
    assert entity_with_only_mac.unique_id == "aa:bb:cc:dd:ee:ff#profile_token_0"

    assert entity_with_index is not None
    assert entity_with_index.unique_id == "aa:bb:cc:dd:ee:ff#profile_token_1"

    # Make sure the sensor entity is unchanged
    assert entity_sensor is not None
    assert entity_sensor.unique_id == "aa:bb:cc:dd:ee:ff"

    # Make sure the already migrated entity is unchanged
    assert entity_migrated is not None
    assert entity_migrated.unique_id == "aa:bb:cc:dd:ee:ff#profile_token_2"
