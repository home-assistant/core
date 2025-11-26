"""Tests for Entity Migration integration setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.entity_migration.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


async def test_setup(hass: HomeAssistant) -> None:
    """Test integration setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Verify the integration is loaded
    assert DOMAIN in hass.config.components

    # Verify the scan service is registered
    assert hass.services.has_service(DOMAIN, "scan")

    # Verify the migrate service is registered
    assert hass.services.has_service(DOMAIN, "migrate")


async def test_service_scan_valid_entity(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scan service with a valid entity ID."""
    # Create a test entity state
    hass.states.async_set("sensor.test_entity", "on")

    result = await hass.services.async_call(
        DOMAIN,
        "scan",
        {"entity_id": "sensor.test_entity"},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    assert result["source_entity_id"] == "sensor.test_entity"
    assert "references" in result
    assert "total_count" in result


async def test_service_scan_invalid_entity_format(
    hass: HomeAssistant,
    init_integration: None,
) -> None:
    """Test scan service with invalid entity ID format."""
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "scan",
            {"entity_id": "invalid_entity_id"},
            blocking=True,
            return_response=True,
        )


async def test_service_migrate_valid_entities(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrate service with valid source and target entities."""
    # Register both entities
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "target_id",
        suggested_object_id="target",
    )
    hass.states.async_set("sensor.source", "on")

    result = await hass.services.async_call(
        DOMAIN,
        "migrate",
        {
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.target",
            "dry_run": True,
        },
        blocking=True,
        return_response=True,
    )

    assert result is not None
    assert result["success"] is True
    assert result["source_entity_id"] == "sensor.source"
    assert result["target_entity_id"] == "sensor.target"
    assert result["dry_run"] is True


async def test_service_migrate_dry_run(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrate service with dry_run option."""
    # Register both entities
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="old_sensor",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "target_id",
        suggested_object_id="new_sensor",
    )
    hass.states.async_set("sensor.old_sensor", "21")

    result = await hass.services.async_call(
        DOMAIN,
        "migrate",
        {
            "source_entity_id": "sensor.old_sensor",
            "target_entity_id": "sensor.new_sensor",
            "dry_run": True,
            "create_backup": False,
        },
        blocking=True,
        return_response=True,
    )

    assert result is not None
    assert result["success"] is True
    assert result["dry_run"] is True
    # In dry run mode, no actual changes should be made
    assert "updated_count" in result


async def test_service_migrate_blocked_by_validation(
    hass: HomeAssistant,
    init_integration: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrate service blocked when target doesn't exist."""
    # Only register source entity
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "migrate",
            {
                "source_entity_id": "sensor.source",
                "target_entity_id": "sensor.nonexistent",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "validation_failed"


async def test_service_migrate_force_bypasses_validation(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrate service with force=true bypasses validation."""
    # Only register source entity (target doesn't exist)
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    hass.states.async_set("sensor.source", "on")

    # Should succeed because force bypasses validation
    result = await hass.services.async_call(
        DOMAIN,
        "migrate",
        {
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.nonexistent",
            "force": True,
            "dry_run": True,
        },
        blocking=True,
        return_response=True,
    )

    assert result is not None
    assert result["success"] is True


async def test_service_migrate_with_create_backup(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrate service with create_backup option."""
    # Register both entities
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "target_id",
        suggested_object_id="target",
    )
    hass.states.async_set("sensor.source", "on")

    result = await hass.services.async_call(
        DOMAIN,
        "migrate",
        {
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.target",
            "dry_run": True,
            "create_backup": True,
        },
        blocking=True,
        return_response=True,
    )

    assert result is not None
    assert result["success"] is True
    # In dry run mode, backup_path should be None even if create_backup is True
    assert result["backup_path"] is None


async def test_service_migrate_invalid_entity_format(
    hass: HomeAssistant,
    init_integration: None,
) -> None:
    """Test migrate service with invalid entity ID format."""
    with pytest.raises(Exception):
        await hass.services.async_call(
            DOMAIN,
            "migrate",
            {
                "source_entity_id": "invalid_format",
                "target_entity_id": "sensor.target",
            },
            blocking=True,
            return_response=True,
        )
