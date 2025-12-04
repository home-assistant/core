"""Compatibility validators for entity migration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.helpers import entity_registry as er

from .models import (
    CompatibilityError,
    CompatibilityResult,
    CompatibilityWarning,
    ErrorType,
    WarningType,
)

_LOGGER = logging.getLogger(__name__)


async def async_validate_compatibility(
    hass: HomeAssistant,
    source_entity_id: str,
    target_entity_id: str,
) -> CompatibilityResult:
    """Validate compatibility between source and target entities.

    Checks for:
    - Valid entity ID format
    - Target entity exists
    - Domain compatibility
    - Device class compatibility
    - Unit of measurement compatibility

    Args:
        hass: Home Assistant instance.
        source_entity_id: The entity ID to migrate from.
        target_entity_id: The entity ID to migrate to.

    Returns:
        CompatibilityResult with validation outcome, warnings, and errors.
    """
    warnings: list[CompatibilityWarning] = []
    blocking_errors: list[CompatibilityError] = []

    # Validate entity ID formats
    if not valid_entity_id(source_entity_id):
        blocking_errors.append(
            CompatibilityError(
                error_type=ErrorType.INVALID_ENTITY_ID,
                message=f"Invalid source entity ID format: {source_entity_id}",
            )
        )

    if not valid_entity_id(target_entity_id):
        blocking_errors.append(
            CompatibilityError(
                error_type=ErrorType.INVALID_ENTITY_ID,
                message=f"Invalid target entity ID format: {target_entity_id}",
            )
        )

    # If entity IDs are invalid, return early
    if blocking_errors:
        return CompatibilityResult(
            valid=False,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            warnings=warnings,
            blocking_errors=blocking_errors,
        )

    entity_registry = er.async_get(hass)

    # Check if target entity exists
    target_error = _check_target_exists(entity_registry, target_entity_id)
    if target_error:
        blocking_errors.append(target_error)

    # Check domain match
    domain_warning = _check_domain_match(source_entity_id, target_entity_id)
    if domain_warning:
        warnings.append(domain_warning)

    # Check device class match (only if target exists)
    if not target_error:
        device_class_warning = _check_device_class_match(
            hass, entity_registry, source_entity_id, target_entity_id
        )
        if device_class_warning:
            warnings.append(device_class_warning)

        # Check unit of measurement match
        unit_warning = _check_unit_match(hass, source_entity_id, target_entity_id)
        if unit_warning:
            warnings.append(unit_warning)

    valid = len(blocking_errors) == 0

    _LOGGER.debug(
        "Validation result for %s -> %s: valid=%s, warnings=%d, errors=%d",
        source_entity_id,
        target_entity_id,
        valid,
        len(warnings),
        len(blocking_errors),
    )

    return CompatibilityResult(
        valid=valid,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        warnings=warnings,
        blocking_errors=blocking_errors,
    )


def _check_target_exists(
    entity_registry: er.EntityRegistry,
    target_entity_id: str,
) -> CompatibilityError | None:
    """Check if the target entity exists in the entity registry.

    Args:
        entity_registry: The entity registry.
        target_entity_id: The target entity ID to check.

    Returns:
        CompatibilityError if target doesn't exist, None otherwise.
    """
    entry = entity_registry.async_get(target_entity_id)
    if entry is None:
        return CompatibilityError(
            error_type=ErrorType.TARGET_NOT_FOUND,
            message=(
                f"Target entity '{target_entity_id}' does not exist in the "
                "entity registry. Migration cannot proceed without a valid target."
            ),
        )
    return None


def _check_domain_match(
    source_entity_id: str,
    target_entity_id: str,
) -> CompatibilityWarning | None:
    """Check if source and target entities have the same domain.

    Args:
        source_entity_id: The source entity ID.
        target_entity_id: The target entity ID.

    Returns:
        CompatibilityWarning if domains don't match, None otherwise.
    """
    source_domain = source_entity_id.split(".")[0]
    target_domain = target_entity_id.split(".")[0]

    if source_domain != target_domain:
        return CompatibilityWarning(
            warning_type=WarningType.DOMAIN_MISMATCH,
            message=(
                f"Domain mismatch: Source entity is '{source_domain}' but target "
                f"is '{target_domain}'. This may cause automations or scripts "
                "to behave unexpectedly."
            ),
            source_value=source_domain,
            target_value=target_domain,
        )
    return None


def _check_device_class_match(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    source_entity_id: str,
    target_entity_id: str,
) -> CompatibilityWarning | None:
    """Check if source and target entities have the same device class.

    Args:
        hass: Home Assistant instance.
        entity_registry: The entity registry.
        source_entity_id: The source entity ID.
        target_entity_id: The target entity ID.

    Returns:
        CompatibilityWarning if device classes don't match, None otherwise.
    """
    source_entry = entity_registry.async_get(source_entity_id)
    target_entry = entity_registry.async_get(target_entity_id)

    # Get device class from registry entry or state attributes
    source_device_class = _get_device_class(hass, source_entry, source_entity_id)
    target_device_class = _get_device_class(hass, target_entry, target_entity_id)

    # Only warn if both have device classes and they differ
    if (
        source_device_class is not None
        and target_device_class is not None
        and source_device_class != target_device_class
    ):
        return CompatibilityWarning(
            warning_type=WarningType.DEVICE_CLASS_MISMATCH,
            message=(
                f"Device class mismatch: Source entity has device class "
                f"'{source_device_class}' but target has '{target_device_class}'. "
                "This may affect how the entity is displayed and categorized."
            ),
            source_value=source_device_class,
            target_value=target_device_class,
        )
    return None


def _get_device_class(
    hass: HomeAssistant,
    entity_entry: er.RegistryEntry | None,
    entity_id: str,
) -> str | None:
    """Get the device class for an entity.

    Args:
        hass: Home Assistant instance.
        entity_entry: The entity registry entry (if available).
        entity_id: The entity ID.

    Returns:
        The device class as a string, or None if not set.
    """
    # First try to get from registry entry (user-customized or original)
    if entity_entry is not None:
        # device_class is user-customized, original_device_class is from integration
        device_class = entity_entry.device_class or entity_entry.original_device_class
        if device_class is not None:
            return str(device_class)

    # Fall back to state attributes
    state = hass.states.get(entity_id)
    if state is not None:
        device_class = state.attributes.get("device_class")
        if device_class is not None:
            return str(device_class)

    return None


def _check_unit_match(
    hass: HomeAssistant,
    source_entity_id: str,
    target_entity_id: str,
) -> CompatibilityWarning | None:
    """Check if source and target entities have the same unit of measurement.

    Args:
        hass: Home Assistant instance.
        source_entity_id: The source entity ID.
        target_entity_id: The target entity ID.

    Returns:
        CompatibilityWarning if units don't match, None otherwise.
    """
    source_state = hass.states.get(source_entity_id)
    target_state = hass.states.get(target_entity_id)

    source_unit = (
        source_state.attributes.get("unit_of_measurement")
        if source_state
        else None
    )
    target_unit = (
        target_state.attributes.get("unit_of_measurement")
        if target_state
        else None
    )

    # Only warn if both have units and they differ
    if (
        source_unit is not None
        and target_unit is not None
        and source_unit != target_unit
    ):
        return CompatibilityWarning(
            warning_type=WarningType.UNIT_MISMATCH,
            message=(
                f"Unit of measurement mismatch: Source entity uses '{source_unit}' "
                f"but target uses '{target_unit}'. Automations comparing values "
                "may need adjustment."
            ),
            source_value=source_unit,
            target_value=target_unit,
        )
    return None
