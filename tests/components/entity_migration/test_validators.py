"""Tests for Entity Migration validators."""

from __future__ import annotations

import pytest

from homeassistant.components.entity_migration.models import (
    ErrorType,
    WarningType,
)
from homeassistant.components.entity_migration.validators import (
    _check_device_class_match,
    _check_domain_match,
    _check_target_exists,
    _check_unit_match,
    async_validate_compatibility,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_validate_invalid_source_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test validation with invalid source entity ID format."""
    result = await async_validate_compatibility(
        hass,
        source_entity_id="invalid_entity_id",
        target_entity_id="sensor.target",
    )

    assert result.valid is False
    assert len(result.blocking_errors) >= 1
    assert any(
        e.error_type == ErrorType.INVALID_ENTITY_ID for e in result.blocking_errors
    )


async def test_validate_invalid_target_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test validation with invalid target entity ID format."""
    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="not_a_valid_id",
    )

    assert result.valid is False
    assert len(result.blocking_errors) >= 1
    assert any(
        e.error_type == ErrorType.INVALID_ENTITY_ID for e in result.blocking_errors
    )


async def test_validate_target_not_found(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test validation when target entity doesn't exist."""
    # Register only source entity
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )

    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="sensor.nonexistent",
    )

    assert result.valid is False
    assert len(result.blocking_errors) == 1
    assert result.blocking_errors[0].error_type == ErrorType.TARGET_NOT_FOUND
    assert "does not exist" in result.blocking_errors[0].message


async def test_validate_domain_mismatch_warning(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test validation warns about domain mismatch."""
    # Register both entities with different domains
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "target_id",
        suggested_object_id="target",
    )

    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="binary_sensor.target",
    )

    # Should be valid (domain mismatch is a warning, not an error)
    assert result.valid is True
    assert len(result.warnings) >= 1
    assert any(w.warning_type == WarningType.DOMAIN_MISMATCH for w in result.warnings)

    domain_warning = next(
        w for w in result.warnings if w.warning_type == WarningType.DOMAIN_MISMATCH
    )
    assert domain_warning.source_value == "sensor"
    assert domain_warning.target_value == "binary_sensor"


async def test_validate_device_class_mismatch_warning(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test validation warns about device class mismatch."""
    # Register both entities with different device classes
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
        original_device_class="temperature",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "target_id",
        suggested_object_id="target",
        original_device_class="humidity",
    )

    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="sensor.target",
    )

    assert result.valid is True
    assert any(
        w.warning_type == WarningType.DEVICE_CLASS_MISMATCH for w in result.warnings
    )

    device_class_warning = next(
        w
        for w in result.warnings
        if w.warning_type == WarningType.DEVICE_CLASS_MISMATCH
    )
    assert device_class_warning.source_value == "temperature"
    assert device_class_warning.target_value == "humidity"


async def test_validate_unit_mismatch_warning(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test validation warns about unit of measurement mismatch."""
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

    # Set state with different units
    hass.states.async_set(
        "sensor.source", "25", {"unit_of_measurement": "°C"}
    )
    hass.states.async_set(
        "sensor.target", "77", {"unit_of_measurement": "°F"}
    )

    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="sensor.target",
    )

    assert result.valid is True
    assert any(w.warning_type == WarningType.UNIT_MISMATCH for w in result.warnings)

    unit_warning = next(
        w for w in result.warnings if w.warning_type == WarningType.UNIT_MISMATCH
    )
    assert unit_warning.source_value == "°C"
    assert unit_warning.target_value == "°F"


async def test_validate_compatible_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test validation passes for compatible entities."""
    # Register both entities with same domain and device class
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
        original_device_class="temperature",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "target_id",
        suggested_object_id="target",
        original_device_class="temperature",
    )

    # Set state with same units
    hass.states.async_set(
        "sensor.source", "25", {"unit_of_measurement": "°C"}
    )
    hass.states.async_set(
        "sensor.target", "26", {"unit_of_measurement": "°C"}
    )

    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="sensor.target",
    )

    assert result.valid is True
    assert len(result.warnings) == 0
    assert len(result.blocking_errors) == 0


async def test_validate_result_contains_entity_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that validation result contains source and target entity IDs."""
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

    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="sensor.target",
    )

    assert result.source_entity_id == "sensor.source"
    assert result.target_entity_id == "sensor.target"


async def test_validate_result_as_dict(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test CompatibilityResult as_dict serialization."""
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "target_id",
        suggested_object_id="target",
    )

    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="binary_sensor.target",
    )

    result_dict = result.as_dict()

    assert "valid" in result_dict
    assert "source_entity_id" in result_dict
    assert "target_entity_id" in result_dict
    assert "warnings" in result_dict
    assert "blocking_errors" in result_dict
    assert isinstance(result_dict["warnings"], list)
    assert isinstance(result_dict["blocking_errors"], list)

    # Check warning serialization
    if result_dict["warnings"]:
        warning = result_dict["warnings"][0]
        assert "warning_type" in warning
        assert "message" in warning
        assert "source_value" in warning
        assert "target_value" in warning


def test_check_domain_match_same_domain() -> None:
    """Test domain check returns None for matching domains."""
    result = _check_domain_match("sensor.test1", "sensor.test2")
    assert result is None


def test_check_domain_match_different_domains() -> None:
    """Test domain check returns warning for different domains."""
    result = _check_domain_match("sensor.test", "binary_sensor.test")
    assert result is not None
    assert result.warning_type == WarningType.DOMAIN_MISMATCH
    assert result.source_value == "sensor"
    assert result.target_value == "binary_sensor"


def test_check_target_exists_found(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test target exists check returns None when target exists."""
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "target_id",
        suggested_object_id="target",
    )

    result = _check_target_exists(entity_registry, "sensor.target")
    assert result is None


def test_check_target_exists_not_found(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test target exists check returns error when target doesn't exist."""
    result = _check_target_exists(entity_registry, "sensor.nonexistent")
    assert result is not None
    assert result.error_type == ErrorType.TARGET_NOT_FOUND


async def test_check_device_class_from_state_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device class check uses state attributes when registry doesn't have it."""
    # Register entities without device class in registry
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

    # Set device class via state attributes
    hass.states.async_set(
        "sensor.source", "25", {"device_class": "temperature"}
    )
    hass.states.async_set(
        "sensor.target", "50", {"device_class": "humidity"}
    )

    source_entry = entity_registry.async_get("sensor.source")
    target_entry = entity_registry.async_get("sensor.target")

    result = _check_device_class_match(
        hass, entity_registry, "sensor.source", "sensor.target"
    )

    assert result is not None
    assert result.warning_type == WarningType.DEVICE_CLASS_MISMATCH
    assert result.source_value == "temperature"
    assert result.target_value == "humidity"


async def test_check_unit_match_no_units(
    hass: HomeAssistant,
) -> None:
    """Test unit check returns None when entities have no units."""
    hass.states.async_set("sensor.source", "on")
    hass.states.async_set("sensor.target", "off")

    result = _check_unit_match(hass, "sensor.source", "sensor.target")
    assert result is None


async def test_check_unit_match_same_units(
    hass: HomeAssistant,
) -> None:
    """Test unit check returns None when units match."""
    hass.states.async_set(
        "sensor.source", "25", {"unit_of_measurement": "°C"}
    )
    hass.states.async_set(
        "sensor.target", "26", {"unit_of_measurement": "°C"}
    )

    result = _check_unit_match(hass, "sensor.source", "sensor.target")
    assert result is None


async def test_check_unit_match_different_units(
    hass: HomeAssistant,
) -> None:
    """Test unit check returns warning when units differ."""
    hass.states.async_set(
        "sensor.source", "25", {"unit_of_measurement": "°C"}
    )
    hass.states.async_set(
        "sensor.target", "77", {"unit_of_measurement": "°F"}
    )

    result = _check_unit_match(hass, "sensor.source", "sensor.target")
    assert result is not None
    assert result.warning_type == WarningType.UNIT_MISMATCH
    assert result.source_value == "°C"
    assert result.target_value == "°F"


async def test_validate_multiple_warnings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test validation collects multiple warnings."""
    # Register entities with different domains and device classes
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
        original_device_class="temperature",
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "target_id",
        suggested_object_id="target",
        original_device_class="motion",
    )

    result = await async_validate_compatibility(
        hass,
        source_entity_id="sensor.source",
        target_entity_id="binary_sensor.target",
    )

    assert result.valid is True
    # Should have at least domain mismatch warning
    assert len(result.warnings) >= 1
    warning_types = [w.warning_type for w in result.warnings]
    assert WarningType.DOMAIN_MISMATCH in warning_types
