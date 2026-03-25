"""Helper functions for Span Panel integration."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from span_panel_api import SpanCircuitSnapshot, SpanEvseSnapshot, SpanPanelSnapshot

from homeassistant.components.persistent_notification import async_create
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import DOMAIN, USE_CIRCUIT_NUMBERS, USE_DEVICE_PREFIX
from .util import snapshot_to_device_info

if TYPE_CHECKING:
    from .coordinator import SpanPanelCoordinator

_LOGGER = logging.getLogger(__name__)

# Global suffix mappings for API description keys to user-friendly/entity suffixes
# These mappings drive consistent unique_id/entity_id suffixes across all sensors,
# including Net Energy and import/export flows, and are used for reverse lookups.

# Circuit sensor API field mappings (used by get_user_friendly_suffix)
# Includes power, produced/consumed, net energy, and import/export energy
CIRCUIT_SUFFIX_MAPPING = {
    "instantPowerW": "power",
    "producedEnergyWh": "energy_produced",
    "consumedEnergyWh": "energy_consumed",
    "netEnergyWh": "energy_net",
    "importedEnergyWh": "energy_imported",
    "exportedEnergyWh": "energy_exported",
    "circuit_priority": "priority",
    "current": "current",
    "breaker_rating": "breaker_rating",
}

# Panel sensor API field mappings (used by get_user_friendly_suffix)
# Includes main meter/feedthrough produced, consumed, and net energy
PANEL_SUFFIX_MAPPING = {
    "instantGridPowerW": "grid_power",  # Descriptive to differentiate from other power types
    "feedthroughPowerW": "feed_through_power",
    "batteryPowerW": "battery_power",
    "pvPowerW": "pv_power",
    "gridPowerFlowW": "grid_power_flow",
    "sitePowerW": "site_power",
    "mainMeterEnergyProducedWh": "main_meter_energy_produced",  # Consistent naming
    "mainMeterEnergyConsumedWh": "main_meter_energy_consumed",  # Consistent naming
    "mainMeterNetEnergyWh": "main_meter_energy_net",  # Consistent naming
    "feedthroughEnergyProducedWh": "feed_through_energy_produced",  # Consistent naming
    "feedthroughEnergyConsumedWh": "feed_through_energy_consumed",  # Consistent naming
    "feedthroughNetEnergyWh": "feed_through_energy_net",  # Consistent naming
    "batteryPercentage": "battery_percentage",
}

# Panel entity suffix mappings (used by get_panel_entity_suffix)
# These are the actual entity_id/unique_id suffixes used for panel sensors
# (e.g., "main_meter_net_energy" / "feed_through_net_energy").
PANEL_ENTITY_SUFFIX_MAPPING = {
    "instantGridPowerW": "current_power",
    "feedthroughPowerW": "feed_through_power",
    "batteryPowerW": "battery_power",
    "pvPowerW": "pv_power",
    "gridPowerFlowW": "grid_power_flow",
    "sitePowerW": "site_power",
    "mainMeterEnergyProducedWh": "main_meter_produced_energy",
    "mainMeterEnergyConsumedWh": "main_meter_consumed_energy",
    "mainMeterNetEnergyWh": "main_meter_net_energy",
    "feedthroughEnergyProducedWh": "feed_through_produced_energy",
    "feedthroughEnergyConsumedWh": "feed_through_consumed_energy",
    "feedthroughNetEnergyWh": "feed_through_net_energy",
    "batteryPercentage": "battery_level",
}

# Combined mapping for general suffix lookup
ALL_SUFFIX_MAPPINGS = {**CIRCUIT_SUFFIX_MAPPING, **PANEL_SUFFIX_MAPPING}


def get_api_description_key_from_suffix(suffix: str) -> str | None:
    """Reverse map from user-friendly suffix back to API description key.

    This is used for migration when we need to extract the original API description key
    from an entity_id suffix to call the helper functions correctly.

    Args:
        suffix: User-friendly suffix extracted from entity_id (e.g., "power", "energy_produced")

    Returns:
        API description key (e.g., "instantPowerW", "producedEnergyWh") or None if not found

    Examples:
        get_api_description_key_from_suffix("power") → "instantPowerW"
        get_api_description_key_from_suffix("energy_produced") → "producedEnergyWh"
        get_api_description_key_from_suffix("current_power") → "instantGridPowerW"

    """
    # Panel entity suffix mappings take precedence over panel and circuit suffixes.
    reverse_mapping = {
        **{
            user_suffix: api_key
            for api_key, user_suffix in CIRCUIT_SUFFIX_MAPPING.items()
        },
        **{
            user_suffix: api_key
            for api_key, user_suffix in PANEL_SUFFIX_MAPPING.items()
        },
        **{
            entity_suffix: api_key
            for api_key, entity_suffix in PANEL_ENTITY_SUFFIX_MAPPING.items()
        },
    }

    return reverse_mapping.get(suffix)


def get_suffix_from_sensor_key(sensor_key: str) -> str:
    """Extract the suffix from a sensor key for use with entity ID helpers.

    Args:
        sensor_key: Sensor key like "span_abc123_solar_inverter_power" or "span_abc123_house_total_consumption"

    Returns:
        User-friendly suffix like "power" or "consumption"

    Examples:
        get_suffix_from_sensor_key("span_abc123_solar_inverter_power") → "power"
        get_suffix_from_sensor_key("span_abc123_solar_inverter_energy_produced") → "energy_produced"
        get_suffix_from_sensor_key("span_abc123_house_total_consumption") → "consumption"

    """
    # Remove device prefix (span_{serial}_) from sensor key
    # Sensor keys follow pattern: span_{serial}_{actual_sensor_name}
    parts = sensor_key.split("_")
    if len(parts) >= 3 and parts[0] == "span":
        # Reconstruct the sensor name without the device prefix
        sensor_name = "_".join(parts[2:])
    else:
        # Fallback if pattern doesn't match expected format
        sensor_name = sensor_key

    # For solar sensors, the suffix is the last part after "solar_inverter_"
    if sensor_name.startswith("solar_inverter_"):
        return sensor_name.replace("solar_inverter_", "")

    # For other sensors, the suffix is typically the last part or last few parts
    # Look for well-established suffix patterns
    established_suffixes = [
        "energy_produced",
        "energy_consumed",
        "energy_net",
        "current_power",
        "grid_power",
        "total_power",
        "instant_power",
        "consumption",
        "production",
        "power",
        "energy",
    ]

    # Check if the sensor name ends with any established suffix
    for suffix in established_suffixes:
        if sensor_name.endswith(suffix):
            return suffix

    # If no established pattern matches, return the last part after the last underscore
    name_parts = sensor_name.split("_")
    return name_parts[-1] if name_parts else sensor_name


def is_panel_level_sensor_key(sensor_key: str) -> bool:
    """Check if a sensor key represents a panel-level sensor.

    Panel-level sensors have the form: span_{device_identifier}_{sensor_type}
    Circuit sensors have the form: span_{device_identifier}_{circuit_id}_{sensor_type}

    Args:
        sensor_key: Sensor key to check (e.g., "span_span12345678_current_power" or
            "span_span12345678_12ce227695cd44338864b0ef2ec4168b_instantPowerW").

    Returns:
        True if this is a panel-level sensor (no circuit ID)

    Examples:
        is_panel_level_sensor_key("span_span12345678_current_power") → True
        is_panel_level_sensor_key(
            "span_span12345678_12ce227695cd44338864b0ef2ec4168b_instantPowerW"
        ) → False

    """

    # Must start with "span_"
    if not sensor_key.startswith("span_"):
        return False

    # Look for UUID pattern (32 hex characters) anywhere in the string after "span_"
    # Circuit IDs in SPAN are typically formatted as 32 lowercase hex characters without dashes
    uuid_pattern = re.compile(r"_[a-f0-9]{32}_")

    # If we find a UUID pattern, this is a circuit sensor
    if uuid_pattern.search(sensor_key):
        return False
    # No UUID pattern found, this is a panel-level sensor
    return True


def construct_panel_synthetic_entity_id(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    platform: str,
    suffix: str,
    device_name: str,
    unique_id: str | None = None,
) -> str | None:
    """Construct entity ID for synthetic panel-level sensors with device prefix logic.

    Args:
        coordinator: The coordinator instance
        snapshot: The panel snapshot data
        platform: Platform name ("sensor", etc.)
        suffix: Entity-specific suffix ("current_power", etc.)
        device_name: Device name for the panel
        unique_id: The unique ID for this entity (None to skip registry lookup)

    Returns:
        Constructed entity ID string or None if device info unavailable

    """
    # Check registry first only if unique_id is provided
    if unique_id is not None:
        entity_registry = er.async_get(coordinator.hass)
        existing_entity_id = entity_registry.async_get_entity_id(
            platform, DOMAIN, unique_id
        )
        if existing_entity_id:
            return existing_entity_id
        # FATAL ERROR: Expected unique_id not found in registry
        raise ValueError(
            f"REGISTRY LOOKUP ERROR: Expected unique_id '{unique_id}' not found in registry. "
            f"This indicates a migration or configuration mismatch."
        )

    config_entry = coordinator.config_entry
    if not device_name:
        return None
    use_device_prefix = config_entry.options.get(USE_DEVICE_PREFIX, True)
    parts = []
    if use_device_prefix:
        # Sanitize device name for entity ID use
        sanitized_device_name = slugify(device_name)
        parts.append(sanitized_device_name)
    parts.append(suffix)
    return f"{platform}.{'_'.join(parts)}"


def construct_240v_synthetic_entity_id(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    platform: str,
    suffix: str,
    friendly_name: str,
    tab1: int = 0,
    tab2: int = 0,
    unique_id: str | None = None,
) -> str | None:
    """Construct entity ID for synthetic 240V circuits using tab numbers.

    Args:
        coordinator: The coordinator instance
        snapshot: The panel snapshot data
        platform: Platform name ("sensor", "switch", "select")
        suffix: Entity-specific suffix ("power", "energy_produced", etc.)
        friendly_name: Descriptive name for this synthetic circuit
        tab1: First tab number (0 if not used)
        tab2: Second tab number (0 if not used)
        unique_id: The unique ID for this entity (None to skip registry lookup)

    Returns:
        Constructed entity ID string or None if device info unavailable

    """
    # Validate that we have exactly 2 tabs for 240V circuits
    if tab1 <= 0 or tab2 <= 0:
        raise ValueError(
            f"240V synthetic entity requires exactly 2 tabs, got tab1={tab1}, tab2={tab2}"
        )

    # Build tab numbers list
    tab_numbers = [tab1, tab2]

    # Use the multi-circuit helper
    return construct_multi_circuit_entity_id(
        coordinator=coordinator,
        snapshot=snapshot,
        platform=platform,
        suffix=suffix,
        circuit_numbers=tab_numbers,
        friendly_name=friendly_name,
        unique_id=unique_id,
    )


def construct_120v_synthetic_entity_id(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    platform: str,
    suffix: str,
    friendly_name: str,
    tab: int = 0,
    unique_id: str | None = None,
) -> str | None:
    """Construct entity ID for synthetic 120V circuits using tab number.

    Args:
        coordinator: The coordinator instance
        snapshot: The panel snapshot data
        platform: Platform name ("sensor", "switch", "select")
        suffix: Entity-specific suffix ("power", "energy_produced", etc.)
        friendly_name: Descriptive name for this synthetic circuit
        tab: Tab number
        unique_id: The unique ID for this entity (None to skip registry lookup)

    Returns:
        Constructed entity ID string or None if device info unavailable

    """
    # Validate that we have exactly 1 tab for 120V circuits
    if tab <= 0:
        raise ValueError(f"120V synthetic entity requires exactly 1 tab, got tab={tab}")

    # Use the multi-circuit helper with only one tab
    return construct_multi_circuit_entity_id(
        coordinator=coordinator,
        snapshot=snapshot,
        platform=platform,
        suffix=suffix,
        circuit_numbers=[tab],
        friendly_name=friendly_name,
        unique_id=unique_id,
    )


def get_user_friendly_suffix(description_key: str) -> str:
    """Convert API description keys to user-friendly suffixes for consistent naming."""
    # If we have a direct mapping, use it
    if description_key in ALL_SUFFIX_MAPPINGS:
        return ALL_SUFFIX_MAPPINGS[description_key]

    # Otherwise, sanitize by converting dots to underscores and making lowercase
    return description_key.replace(".", "_").lower()


def build_circuit_unique_id(serial: str, circuit_id: str, description_key: str) -> str:
    """Build unique ID for circuit sensors using consistent pattern (pure function).

    Args:
        serial: Panel serial number
        circuit_id: Circuit ID from panel API (UUID or tab number)
        description_key: Sensor description key (e.g., "instantPowerW")

    Returns:
        Unique ID like "span_{serial}_{circuit_id}_{consistent_suffix}"

    """
    consistent_suffix = get_user_friendly_suffix(description_key)
    return f"span_{serial.lower()}_{circuit_id}_{consistent_suffix}"


def get_panel_entity_suffix(description_key: str) -> str:
    """Convert panel API description keys to entity ID suffixes for unique ID consistency.

    This ensures panel unique IDs use the same suffix as entity IDs for consistency.
    """
    # If we have a direct mapping, use it
    if description_key in PANEL_ENTITY_SUFFIX_MAPPING:
        return PANEL_ENTITY_SUFFIX_MAPPING[description_key]

    # Otherwise, fall back to the general suffix mapping
    return get_user_friendly_suffix(description_key)


def build_panel_unique_id(serial: str, description_key: str) -> str:
    """Build unique ID for panel-level sensors using entity ID suffix pattern (pure function).

    Args:
        serial: Panel serial number
        description_key: Sensor description key (e.g., "instantGridPowerW")

    Returns:
        Unique ID like "span_{serial}_{entity_suffix}" (matches entity ID suffix)

    """
    entity_suffix = get_panel_entity_suffix(description_key)
    return f"span_{serial.lower()}_{entity_suffix}"


def build_switch_unique_id(serial: str, circuit_id: str) -> str:
    """Build unique ID for switch entities using consistent pattern (pure function).

    Args:
        serial: Panel serial number
        circuit_id: Circuit ID from panel API

    Returns:
        Unique ID like "span_{serial}_relay_{circuit_id}"

    """
    return f"span_{serial}_relay_{circuit_id}"


def build_binary_sensor_unique_id(serial: str, description_key: str) -> str:
    """Build unique ID for binary sensor entities using consistent pattern (pure function).

    Args:
        serial: Panel serial number
        description_key: Sensor description key (e.g., "doorState")

    Returns:
        Unique ID like "span_{serial}_{description_key}"

    """
    return f"span_{serial}_{description_key}"


def build_select_unique_id(serial: str, select_id: str) -> str:
    """Build unique ID for select entities using consistent pattern (pure function).

    Args:
        serial: Panel serial number
        select_id: Select entity identifier

    Returns:
        Unique ID like "span_{serial}_select_{select_id}"

    """
    return f"span_{serial}_select_{select_id}"


def build_bess_unique_id(serial: str, description_key: str) -> str:
    """Build unique ID for BESS sensor entities (pure function).

    Returns: "span_{serial}_bess_{description_key}"
    """
    return f"span_{serial}_bess_{description_key}"


def build_evse_unique_id(serial: str, evse_id: str, description_key: str) -> str:
    """Build unique ID for EVSE sensor/binary_sensor entities (pure function).

    Returns: "span_{serial}_evse_{evse_id}_{description_key}"
    """
    return f"span_{serial}_evse_{evse_id}_{description_key}"


def resolve_evse_display_suffix(
    evse: SpanEvseSnapshot,
    snapshot: SpanPanelSnapshot,
    use_circuit_numbers: bool,
) -> str | None:
    """Resolve the display suffix for an EVSE device name.

    Friendly names mode: returns the fed circuit's panel name (e.g., "Garage").
    Circuit numbers mode: returns the EVSE serial number (e.g., "SN-EVSE-001").
    Returns None when no meaningful suffix is available (prevents empty parens).
    """
    if use_circuit_numbers:
        serial: str | None = evse.serial_number
        return serial
    fed_circuit = snapshot.circuits.get(evse.feed_circuit_id)
    if fed_circuit and fed_circuit.name:
        name: str = fed_circuit.name
        return name
    return None


def construct_synthetic_unique_id(serial: str, sensor_name: str) -> str:
    """Build unique ID for synthetic sensors using consistent pattern (pure function).

    Args:
        serial: Panel serial number
        sensor_name: Complete sensor name with suffix (e.g., "solar_inverter_power")

    Returns:
        Unique ID like "span_{serial}_{sensor_name}"

    """
    return f"span_{serial.lower()}_{sensor_name}"


def construct_sensor_set_id(device_identifier: str) -> str:
    """Build sensor set ID for synthetic sensors using consistent pattern (pure function).

    Args:
        device_identifier: Per-entry panel identifier (panel serial from the API).

    Returns:
        Sensor set ID like "{device_identifier}_sensors"

    """
    return f"{device_identifier}_sensors"


def _get_device_identifier_for_unique_ids(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    device_name: str | None = None,
) -> str:
    """Return the panel serial used as the device segment in unique_ids."""
    serial: str = snapshot.serial_number
    return serial


def construct_panel_unique_id_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    description_key: str,
    device_name: str | None = None,
) -> str:
    """Build panel unique_id using the panel serial from the snapshot."""
    identifier = _get_device_identifier_for_unique_ids(
        coordinator, snapshot, device_name
    )
    return build_panel_unique_id(identifier, description_key)


def construct_circuit_unique_id_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    circuit_id: str,
    description_key: str,
    device_name: str | None = None,
) -> str:
    """Build circuit unique_id using the panel serial from the snapshot."""
    identifier = _get_device_identifier_for_unique_ids(
        coordinator, snapshot, device_name
    )
    return build_circuit_unique_id(identifier, circuit_id, description_key)


def build_switch_unique_id_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    circuit_id: str,
    device_name: str | None = None,
) -> str:
    """Build switch unique_id using the panel serial from the snapshot."""
    identifier = _get_device_identifier_for_unique_ids(
        coordinator, snapshot, device_name
    )
    return build_switch_unique_id(identifier, circuit_id)


def build_select_unique_id_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    select_id: str,
    device_name: str | None = None,
) -> str:
    """Build select unique_id using the panel serial from the snapshot."""
    identifier = _get_device_identifier_for_unique_ids(
        coordinator, snapshot, device_name
    )
    return build_select_unique_id(identifier, select_id)


def build_binary_sensor_unique_id_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    description_key: str,
    device_name: str | None = None,
) -> str:
    """Build binary_sensor unique_id using the panel serial from the snapshot."""
    identifier = _get_device_identifier_for_unique_ids(
        coordinator, snapshot, device_name
    )
    return build_binary_sensor_unique_id(identifier, description_key)


def construct_synthetic_unique_id_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    sensor_name: str,
    device_name: str | None = None,
) -> str:
    """Build synthetic sensor unique_id using the panel serial from the snapshot."""
    identifier = _get_device_identifier_for_unique_ids(
        coordinator, snapshot, device_name
    )
    return construct_synthetic_unique_id(identifier, sensor_name)


def build_evse_unique_id_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    evse_id: str,
    description_key: str,
    device_name: str | None = None,
) -> str:
    """Build EVSE unique_id using the panel serial from the snapshot."""
    identifier = _get_device_identifier_for_unique_ids(
        coordinator, snapshot, device_name
    )
    return build_evse_unique_id(identifier, evse_id, description_key)


def build_bess_unique_id_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    description_key: str,
    device_name: str | None = None,
) -> str:
    """Build BESS unique_id using the panel serial from the snapshot."""
    identifier = _get_device_identifier_for_unique_ids(
        coordinator, snapshot, device_name
    )
    return build_bess_unique_id(identifier, description_key)


def get_device_identifier_for_entry(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    device_name: str | None = None,
) -> str:
    """Public helper to get the per-entry device identifier used in unique_ids and storage."""
    return _get_device_identifier_for_unique_ids(coordinator, snapshot, device_name)


def construct_circuit_unique_id(
    snapshot: SpanPanelSnapshot, circuit_id: str, description_key: str
) -> str:
    """Construct unique ID for circuit sensors using consistent pattern.

    Args:
        snapshot: The panel snapshot data
        circuit_id: Circuit ID from panel API (UUID or tab number)
        description_key: Sensor description key (e.g., "instantPowerW")

    Returns:
        Unique ID like "span_{serial}_{circuit_id}_{consistent_suffix}"

    Examples:
        span_abc123_0dad2f16cd514812ae1807b0457d473e_power
        span_abc123_circuit_15_energy_produced

    """
    return build_circuit_unique_id(snapshot.serial_number, circuit_id, description_key)


def construct_panel_unique_id(snapshot: SpanPanelSnapshot, description_key: str) -> str:
    """Construct unique ID for panel-level sensors using consistent pattern.

    Args:
        snapshot: The panel snapshot data
        description_key: Sensor description key (e.g., "instantGridPowerW")

    Returns:
        Unique ID like "span_{serial}_{consistent_suffix}" (uses descriptive consistent names)

    Examples:
        span_abc123_grid_power
        span_abc123_feed_through_power
        span_abc123_dsm_state

    """
    return build_panel_unique_id(snapshot.serial_number, description_key)


def construct_switch_unique_id(snapshot: SpanPanelSnapshot, circuit_id: str) -> str:
    """Construct unique ID for switch entities using consistent pattern.

    Args:
        snapshot: The panel snapshot data
        circuit_id: Circuit ID from panel API

    Returns:
        Unique ID like "span_{serial}_relay_{circuit_id}"

    Examples:
        span_abc123_relay_0dad2f16cd514812ae1807b0457d473e

    """
    return build_switch_unique_id(snapshot.serial_number, circuit_id)


def construct_binary_sensor_unique_id(
    snapshot: SpanPanelSnapshot, description_key: str
) -> str:
    """Construct unique ID for binary sensor entities using consistent pattern.

    Args:
        snapshot: The panel snapshot data
        description_key: Sensor description key (e.g., "doorState")

    Returns:
        Unique ID like "span_{serial}_{description_key}"

    Examples:
        span_abc123_doorState
        span_abc123_eth0Link

    """
    return build_binary_sensor_unique_id(snapshot.serial_number, description_key)


def construct_select_unique_id(snapshot: SpanPanelSnapshot, select_id: str) -> str:
    """Construct unique ID for select entities using consistent pattern.

    Args:
        snapshot: The panel snapshot data
        select_id: Select entity identifier

    Returns:
        Unique ID like "span_{serial}_select_{select_id}"

    Examples:
        span_abc123_select_priority_mode

    """
    return build_select_unique_id(snapshot.serial_number, select_id)


def construct_multi_circuit_entity_id(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    platform: str,
    suffix: str,
    circuit_numbers: list[int],
    friendly_name: str | None = None,
    unique_id: str | None = None,
) -> str | None:
    """Construct entity ID for multi-circuit sensors (like solar inverters).

    Args:
        coordinator: The coordinator instance
        snapshot: The panel snapshot data
        platform: Platform name ("sensor", "switch", "select")
        suffix: Entity-specific suffix ("power", "energy_produced", etc.)
        circuit_numbers: List of circuit numbers this sensor combines
        friendly_name: Descriptive name for this sensor (required if unique_id is None)
        unique_id: The unique ID for this entity (None to skip registry lookup)

    Returns:
        Constructed entity ID string or None if device info unavailable

    """
    # Check registry first only if unique_id is provided
    if unique_id is not None:
        entity_registry = er.async_get(coordinator.hass)
        existing_entity_id = entity_registry.async_get_entity_id(
            platform, DOMAIN, unique_id
        )

        _LOGGER.debug(
            "Multi-circuit helper registry lookup (switches/selects) - unique_id=%s, found_entity_id=%s",
            unique_id,
            existing_entity_id,
        )

        if existing_entity_id:
            return existing_entity_id
        # During migration, unique_id lookup should always succeed
        raise ValueError(
            f"Registry lookup failed for unique_id '{unique_id}' during migration. Entity should exist in registry."
        )
    _LOGGER.debug(
        "Multi-circuit helper (switches/selects) - no unique_id provided, skipping registry lookup"
    )

    # Get device name from config entry data
    device_name = coordinator.config_entry.data.get(
        "device_name", coordinator.config_entry.title
    )
    if not device_name:
        return None

    use_circuit_numbers = coordinator.config_entry.options.get(
        USE_CIRCUIT_NUMBERS, False
    )

    # If no unique_id provided, friendly_name is required when not using circuit numbers
    if unique_id is None and not use_circuit_numbers and not friendly_name:
        _LOGGER.error(
            "Friendly_name is required when unique_id is None and not using circuit numbers for multi-circuit entity"
        )
        return None

    if use_circuit_numbers:
        # Use circuit number pattern: sensor.span_panel_circuit_30_32_power
        if circuit_numbers:
            sorted_circuits = sorted([num for num in circuit_numbers if num > 0])
        else:
            sorted_circuits = []
        if sorted_circuits:
            if len(sorted_circuits) == 1:
                circuit_part = f"circuit_{sorted_circuits[0]}"
            else:
                circuit_list = "_".join(str(num) for num in sorted_circuits)
                circuit_part = f"circuit_{circuit_list}"
        else:
            raise ValueError(
                f"Circuit-based naming is enabled but no valid circuit numbers provided. "
                f"Got circuit_numbers={circuit_numbers}. Multi-circuit entities require valid circuit numbers when USE_CIRCUIT_NUMBERS is True."
            )
    else:
        # Use friendly name pattern: sensor.span_panel_solar_inverter_power
        circuit_part = slugify(friendly_name)

    # Build the entity ID
    use_device_prefix = coordinator.config_entry.options.get(USE_DEVICE_PREFIX, False)
    parts = []

    if use_device_prefix:
        if device_name:
            # Sanitize device name for entity ID use
            sanitized_device_name = slugify(device_name)
            parts.append(sanitized_device_name)

    parts.append(circuit_part)

    # Add suffix if not already in circuit_part
    if suffix and not circuit_part.endswith(f"_{suffix}"):
        parts.append(suffix)

    return f"{platform}.{'_'.join(parts)}"


def construct_single_circuit_entity_id(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    platform: str,
    suffix: str,
    circuit_data: SpanCircuitSnapshot,
    unique_id: str | None = None,
    device_name: str | None = None,
) -> str | None:
    """Construct entity ID for single-circuit sensors.

    Args:
        coordinator: The coordinator instance
        snapshot: The panel snapshot data
        platform: Platform name ("sensor", "switch", "select")
        suffix: Entity-specific suffix ("power", "energy_produced", etc.)
        circuit_data: Circuit data object
        unique_id: The unique ID for this entity (None to skip registry lookup)
        device_name: Device name for entity ID construction (None to use from config entry)

    Returns:
        Constructed entity ID string or None if device info unavailable

    """
    # Check registry first only if unique_id is provided
    if unique_id is not None:
        entity_registry = er.async_get(coordinator.hass)
        existing_entity_id = entity_registry.async_get_entity_id(
            platform, DOMAIN, unique_id
        )

        _LOGGER.debug(
            "Circuit helper registry lookup - unique_id=%s, found_entity_id=%s",
            unique_id,
            existing_entity_id,
        )

        if existing_entity_id:
            return existing_entity_id
        # FATAL ERROR: Expected unique_id not found in registry
        raise ValueError(
            f"REGISTRY LOOKUP ERROR: Expected unique_id '{unique_id}' not found in registry. "
            f"This indicates a migration or configuration mismatch."
        )
    _LOGGER.debug("Circuit helper - no unique_id provided, skipping registry lookup")

    # Get device info
    device_info = snapshot_to_device_info(snapshot, device_name)
    if not device_info or not device_info.get("name"):
        return None

    use_circuit_numbers = coordinator.config_entry.options.get(
        USE_CIRCUIT_NUMBERS, False
    )

    if use_circuit_numbers:
        # Check if this is a 240V circuit (2 tabs) or 120V circuit (1 tab)
        if circuit_data.tabs and len(circuit_data.tabs) == 2:
            # 240V circuit - use both tab numbers
            sorted_tabs = sorted(circuit_data.tabs)
            circuit_part = f"circuit_{sorted_tabs[0]}_{sorted_tabs[1]}"
        elif circuit_data.tabs and len(circuit_data.tabs) == 1:
            # 120V circuit - use single tab number
            circuit_part = f"circuit_{circuit_data.tabs[0]}"
        else:
            # No tabs available — use the API circuit_id as fallback
            circuit_part = (
                f"circuit_{circuit_data.circuit_id}"
                if circuit_data.circuit_id
                else "circuit_unknown"
            )
    # Use friendly name pattern: sensor.span_panel_solar_east_power
    elif circuit_data.name:
        circuit_part = slugify(circuit_data.name)
    else:
        circuit_part = "single_circuit"

    # Build the entity ID (only for non-voltage-specific cases)
    use_device_prefix = coordinator.config_entry.options.get(USE_DEVICE_PREFIX, True)
    parts = []

    if use_device_prefix:
        device_name = device_info.get("name")
        if device_name:
            # Sanitize device name for entity ID use
            sanitized_device_name = slugify(device_name)
            parts.append(sanitized_device_name)

    parts.append(circuit_part)

    # Add suffix if not already in circuit_part
    if suffix and not circuit_part.endswith(f"_{suffix}"):
        parts.append(suffix)

    return f"{platform}.{'_'.join(parts)}"


def construct_panel_entity_id(
    coordinator: SpanPanelCoordinator,
    snapshot: SpanPanelSnapshot,
    platform: str,
    suffix: str,
    device_name: str,
    unique_id: str | None = None,
    use_device_prefix: bool | None = None,
) -> str | None:
    """Construct entity ID for panel-level sensors based on integration configuration flags.

    This function handles entity naming for panel-level entities based on the
    USE_DEVICE_PREFIX configuration flag. It also checks the entity registry
    to respect user customizations when unique_id is provided.

    Args:
        coordinator: The coordinator instance
        snapshot: The panel snapshot data
        platform: Platform name ("sensor", "switch", "select")
        suffix: Entity-specific suffix ("current_power", "feed_through_power", etc.)
        device_name: Device name for the panel
        unique_id: The unique ID for this entity (None to skip registry lookup)
        use_device_prefix: Whether to include device name prefix in entity ID (None to use config option)

    Returns:
        Constructed entity ID string or None if device info unavailable

    """
    # Check registry first only if unique_id is provided
    if unique_id is not None:
        entity_registry = er.async_get(coordinator.hass)
        existing_entity_id = entity_registry.async_get_entity_id(
            platform, DOMAIN, unique_id
        )

        # Debug logging for panel entity registry lookup
        _LOGGER.debug(
            "Panel helper registry lookup - unique_id=%s, found_entity_id=%s",
            unique_id,
            existing_entity_id,
        )

        if existing_entity_id:
            return existing_entity_id

    # Construct default entity_id
    config_entry = coordinator.config_entry

    if not device_name:
        return None

    if use_device_prefix is None:
        use_device_prefix = config_entry.options.get(USE_DEVICE_PREFIX, True)

    # Build entity ID components
    parts = []

    if use_device_prefix:
        # Sanitize device name for entity ID use
        sanitized_device_name = slugify(device_name)
        parts.append(sanitized_device_name)

    parts.append(suffix)

    return f"{platform}.{'_'.join(parts)}"


def construct_unmapped_unique_id(
    snapshot: SpanPanelSnapshot, circuit_number: int | str, suffix: str
) -> str:
    """Construct unique ID for unmapped circuit sensors."""
    # Always use consistent unique ID pattern for unmapped circuits
    # Format: span_{serial}_unmapped_tab_{circuit_number}_{suffix}
    return f"span_{snapshot.serial_number}_unmapped_tab_{circuit_number}_{suffix}"


def construct_unmapped_entity_id(
    snapshot: SpanPanelSnapshot,
    circuit_id: str,
    suffix: str,
    device_name: str | None = None,
) -> str:
    """Construct entity ID for unmapped tab with consistent modern naming.

    Args:
        snapshot: The panel snapshot data
        circuit_id: Circuit ID (e.g., "unmapped_tab_32")
        suffix: Sensor suffix (e.g., "power", "energy_produced")
        device_name: The device name to use for entity ID construction

    Returns:
        Entity ID string like "sensor.span_panel_unmapped_tab_32_power"

    """
    # Always use device prefix for unmapped entities
    # circuit_id is "unmapped_tab_32", add device prefix and suffix to create
    # "sensor.span_panel_unmapped_tab_32_power"
    device_info = snapshot_to_device_info(snapshot, device_name)
    device_name_raw = device_info.get("name")
    _LOGGER.debug(
        "construct_unmapped_entity_id: circuit_id=%s, suffix=%s, device_name_raw=%s",
        circuit_id,
        suffix,
        device_name_raw,
    )
    if device_name_raw:
        # Sanitize device name for entity ID use
        sanitized_device_name = slugify(device_name_raw)
        result = f"sensor.{sanitized_device_name}_{circuit_id}_{suffix}"
        _LOGGER.debug("construct_unmapped_entity_id result with device: %s", result)
        return result
    result = f"sensor.{circuit_id}_{suffix}"
    _LOGGER.debug("construct_unmapped_entity_id result without device: %s", result)
    return result


def get_unmapped_circuit_entity_id(
    snapshot: SpanPanelSnapshot,
    tab_number: int,
    suffix: str,
    device_name: str | None = None,
) -> str | None:
    """Get entity ID for an unmapped circuit based on tab number.

    This helper function constructs the entity ID for native unmapped circuit sensors
    that should already exist in Home Assistant. It's useful for synthetic sensors
    that need to reference these native entities in formulas.

    Args:
        snapshot: The panel snapshot data
        tab_number: The tab number (e.g., 30, 32)
        suffix: The sensor suffix (e.g., "power", "energy_produced", "energy_consumed")
        device_name: The device name to use for entity ID construction

    Returns:
        Entity ID string like "sensor.span_panel_unmapped_tab_30_power"
        or None if the circuit doesn't exist

    Examples:
        get_unmapped_circuit_entity_id(snapshot, 30, "power")
        # Returns: "sensor.span_panel_unmapped_tab_30_power"

        get_unmapped_circuit_entity_id(snapshot, 32, "energy_produced")
        # Returns: "sensor.span_panel_unmapped_tab_32_energy_produced"

    """
    circuit_id = f"unmapped_tab_{tab_number}"

    # Verify the circuit exists in the panel data
    if circuit_id not in snapshot.circuits:
        _LOGGER.debug("Unmapped circuit %s not found in circuits list", circuit_id)
        return None

    result_entity_id = construct_unmapped_entity_id(
        snapshot, circuit_id, suffix, device_name
    )
    _LOGGER.debug("Generated unmapped entity ID: %s", result_entity_id)
    return result_entity_id


def construct_unmapped_friendly_name(
    circuit_number: int | str, sensor_description_name: str
) -> str:
    """Construct friendly name for unmapped circuit sensors."""
    # Format: "Unmapped Tab 32 Consumed Energy"
    return f"Unmapped Tab {circuit_number} {sensor_description_name}"


def construct_panel_friendly_name(description_name: Any) -> str:
    """Construct friendly name for panel-level sensors.

    Args:
        description_name: The sensor description name (can be str, None, or UndefinedType)

    Returns:
        Friendly name string

    """
    return str(description_name) if description_name else ""


def construct_status_friendly_name(description_name: Any) -> str:
    """Construct friendly name for status sensors.

    Args:
        description_name: The sensor description name (can be str, None, or UndefinedType)

    Returns:
        Friendly name string

    """
    return str(description_name) if description_name else ""


async def async_create_span_notification(
    hass: HomeAssistant,
    message: str,
    title: str,
    notification_id: str,
    level: str = "warning",
) -> None:
    """Create a persistent notification for SPAN Panel issues.

    Args:
        hass: Home Assistant instance
        message: Notification message content
        title: Notification title
        notification_id: Unique identifier for the notification
        level: Severity level (info, warning, error)

    """
    _LOGGER.log(
        getattr(logging, level.upper(), logging.WARNING),
        "SPAN Panel %s: %s - %s",
        level,
        title,
        message,
    )

    async_create(
        hass,
        message=message,
        title=title,
        notification_id=notification_id,
    )


def construct_unmapped_circuit_id(circuit_number: int | str) -> str:
    """Construct circuit ID for unmapped circuits.

    This returns just the circuit ID part (e.g., "unmapped_tab_30"), not a full entity ID.
    Used for API circuit references and internal circuit identification.

    Args:
        circuit_number: The tab number (e.g., 30, 32)

    Returns:
        Circuit ID string like "unmapped_tab_30"

    Examples:
        construct_unmapped_circuit_id(30) -> "unmapped_tab_30"
        construct_unmapped_circuit_id(32) -> "unmapped_tab_32"

    """
    return f"unmapped_tab_{circuit_number}"


def construct_circuit_identifier_from_tabs(
    tabs: list[int], circuit_id: str = ""
) -> str:
    """Build a human-readable circuit identifier from tab positions.

    Used as a fallback when a circuit has no panel-assigned name.

    Args:
        tabs: List of tab numbers (1 for 120V, 2 for 240V dipole)
        circuit_id: Fallback identifier when tabs are unavailable

    Returns:
        String like "Circuit 30 32" for 240V or "Circuit 15" for 120V

    """
    if tabs and len(tabs) == 2:
        sorted_tabs = sorted(tabs)
        return f"Circuit {sorted_tabs[0]} {sorted_tabs[1]}"
    if tabs and len(tabs) == 1:
        return f"Circuit {tabs[0]}"
    return f"Circuit {circuit_id}"


def construct_tabs_attribute(circuit: SpanCircuitSnapshot) -> str | None:
    """Construct tabs attribute string from circuit data.

    For US electrical systems, circuits can only have 1 tab (120V) or 2 tabs (240V).

    Args:
        circuit: SpanCircuitSnapshot object with tabs information

    Returns:
        Tabs attribute string like "tabs [30:32]" for 240V or "tabs [28]" for 120V,
        or None if no tabs information is available

    Examples:
        Single tab (120V): "tabs [28]"
        Two tabs (240V): "tabs [30:32]"
        No tabs: None

    """
    if not circuit.tabs:
        return None

    # Sort tabs for consistent ordering
    sorted_tabs = sorted(circuit.tabs)

    if len(sorted_tabs) == 1:
        # Single tab (120V)
        return f"tabs [{sorted_tabs[0]}]"
    if len(sorted_tabs) == 2:
        # Two tabs (240V) - format as range
        return f"tabs [{sorted_tabs[0]}:{sorted_tabs[1]}]"
    # More than 2 tabs is not valid for US electrical system
    _LOGGER.warning(
        "Circuit %s has %d tabs, which is not valid for US electrical system (expected 1 or 2)",
        circuit.circuit_id,
        len(sorted_tabs),
    )
    return None


def parse_tabs_attribute(tabs_attr: str) -> list[int] | None:
    """Parse tabs attribute string back to list of tab numbers.

    For US electrical systems, only 1 tab (120V) or 2 tabs (240V) are valid.

    Args:
        tabs_attr: Tabs attribute string like "tabs [30:32]" or "tabs [28]"

    Returns:
        List of tab numbers, or None if parsing fails or invalid for US electrical system

    Examples:
        "tabs [28]" -> [28] (120V)
        "tabs [30:32]" -> [30, 32] (240V)

    """
    if not tabs_attr or not tabs_attr.startswith("tabs ["):
        return None

    try:
        # Extract content between brackets
        content = tabs_attr[6:-1]  # Remove "tabs [" and "]"

        if ":" in content:
            # Range format: "30:32" (240V)
            start, end = map(int, content.split(":"))
            return [start, end]
        # Single tab: "28" (120V)
        return [int(content)]

    except (ValueError, IndexError) as e:
        _LOGGER.warning("Failed to parse tabs attribute '%s': %s", tabs_attr, e)
        return None


def get_circuit_voltage_type(circuit: SpanCircuitSnapshot) -> str:
    """Determine the voltage type of a circuit based on its tabs.

    For US electrical systems, circuits can only be 120V (1 tab) or 240V (2 tabs).

    Args:
        circuit: SpanCircuitSnapshot object

    Returns:
        Voltage type: "120V" for single tab, "240V" for two tabs, "unknown" otherwise

    """
    if not circuit.tabs:
        return "unknown"

    if len(circuit.tabs) == 1:
        return "120V"
    if len(circuit.tabs) == 2:
        return "240V"
    # More than 2 tabs is not valid for US electrical system
    _LOGGER.warning(
        "Circuit %s has %d tabs, which is not valid for US electrical system (expected 1 or 2)",
        circuit.circuit_id,
        len(circuit.tabs),
    )
    return "unknown"


def get_panel_voltage_attribute() -> int:
    """Get voltage attribute for panel-level sensors.

    US residential electrical panels are standardized as 240V split-phase systems.
    Panel-level sensors (like main meter energy) represent aggregate measurements
    at the full panel voltage.

    Returns:
        Panel voltage in volts (always 240 for US residential panels)

    """
    return 240


def construct_voltage_attribute(circuit: SpanCircuitSnapshot) -> int | None:
    """Construct voltage attribute for a circuit based on tab count.

    For US electrical systems, circuits can only have 1 tab (120V) or 2 tabs (240V).

    Args:
        circuit: SpanCircuitSnapshot object with tabs information

    Returns:
        Voltage in volts (120 for single tab, 240 for double tab), or None if no tabs information

    Examples:
        Single tab (120V): 120
        Two tabs (240V): 240
        No tabs: None

    """
    if not circuit.tabs:
        return None

    if len(circuit.tabs) == 1:
        return 120
    if len(circuit.tabs) == 2:
        return 240
    # More than 2 tabs is not valid for US electrical system
    _LOGGER.warning(
        "Circuit %s has %d tabs, which is not valid for US electrical system (expected 1 or 2)",
        circuit.circuit_id,
        len(circuit.tabs),
    )
    return None


def has_bess(snapshot: SpanPanelSnapshot) -> bool:
    """Detect whether a BESS (battery energy storage system) is commissioned.

    Only soe_percentage is a reliable signal — the power-flows node publishes
    battery=0.0 even on panels without a commissioned BESS.
    """
    return snapshot.battery.soe_percentage is not None


def has_pv(snapshot: SpanPanelSnapshot) -> bool:
    """Detect whether PV (solar) is commissioned."""
    return snapshot.power_flow_pv is not None or any(
        c.device_type == "pv" for c in snapshot.circuits.values()
    )


def has_power_flows(snapshot: SpanPanelSnapshot) -> bool:
    """Detect whether the power-flows node is publishing data."""
    return snapshot.power_flow_site is not None


def has_evse(snapshot: SpanPanelSnapshot) -> bool:
    """Detect whether an EVSE (EV charger) is commissioned."""
    return len(snapshot.evse) > 0


def detect_capabilities(snapshot: SpanPanelSnapshot) -> frozenset[str]:
    """Derive the set of optional capabilities present in the snapshot.

    Used by the coordinator to detect when new hardware (BESS, PV, EVSE) appears
    and trigger a reload so new sensors are created.
    """
    caps: set[str] = set()
    if has_bess(snapshot):
        caps.add("bess")
    if has_pv(snapshot):
        caps.add("pv")
    if has_power_flows(snapshot):
        caps.add("power_flows")
    if has_evse(snapshot):
        caps.add("evse")
    return frozenset(caps)
