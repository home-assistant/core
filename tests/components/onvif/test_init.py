"""Tests for the ONVIF integration __init__ module."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MAC, setup_mock_device

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_migrate_camera_entities_unique_ids(hass: HomeAssistant) -> None:
    """Test that camera entities unique ids get migrated properly."""
    config_entry = MockConfigEntry(domain="onvif", unique_id=MAC)
    config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    entity_with_only_mac = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=MAC,
        config_entry=config_entry,
    )
    entity_with_index = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=f"{MAC}_1",
        config_entry=config_entry,
    )
    # This one should not be migrated (different domain)
    entity_sensor = entity_registry.async_get_or_create(
        domain="sensor",
        platform="onvif",
        unique_id=MAC,
        config_entry=config_entry,
    )
    # This one should not be migrated (already migrated)
    entity_migrated = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=f"{MAC}#profile_token_2",
        config_entry=config_entry,
    )
    # Unparsable index
    entity_unparsable_index = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=f"{MAC}_a",
        config_entry=config_entry,
    )
    # Unexisting index
    entity_unexisting_index = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=f"{MAC}_9",
        config_entry=config_entry,
    )

    with patch("homeassistant.components.onvif.ONVIFDevice") as mock_device:
        setup_mock_device(
            mock_device,
            capabilities=None,
            profiles=[
                MagicMock(token="profile_token_0"),
                MagicMock(token="profile_token_1"),
                MagicMock(token="profile_token_2"),
            ],
        )
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_with_only_mac = entity_registry.async_get(entity_with_only_mac.entity_id)
    entity_with_index = entity_registry.async_get(entity_with_index.entity_id)
    entity_sensor = entity_registry.async_get(entity_sensor.entity_id)
    entity_migrated = entity_registry.async_get(entity_migrated.entity_id)

    assert entity_with_only_mac is not None
    assert entity_with_only_mac.unique_id == f"{MAC}#profile_token_0"

    assert entity_with_index is not None
    assert entity_with_index.unique_id == f"{MAC}#profile_token_1"

    # Make sure the sensor entity is unchanged
    assert entity_sensor is not None
    assert entity_sensor.unique_id == MAC

    # Make sure the already migrated entity is unchanged
    assert entity_migrated is not None
    assert entity_migrated.unique_id == f"{MAC}#profile_token_2"

    # Make sure the unparsable index entity is unchanged
    assert entity_unparsable_index is not None
    assert entity_unparsable_index.unique_id == f"{MAC}_a"

    # Make sure the unexisting index entity is unchanged
    assert entity_unexisting_index is not None
    assert entity_unexisting_index.unique_id == f"{MAC}_9"
