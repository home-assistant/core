"""Circuit-level sensors for Span Panel integration."""

# pylint: disable=hass-enforce-class-module

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from span_panel_api import SpanCircuitSnapshot, SpanPanelSnapshot

from homeassistant.helpers.device_registry import DeviceInfo

from .const import USE_CIRCUIT_NUMBERS
from .coordinator import SpanPanelCoordinator
from .helpers import (
    construct_circuit_identifier_from_tabs,
    construct_circuit_unique_id_for_entry,
    construct_single_circuit_entity_id,
    construct_tabs_attribute,
    construct_unmapped_friendly_name,
    construct_voltage_attribute,
    get_user_friendly_suffix,
)
from .sensor_base import SpanEnergySensorBase, SpanSensorBase
from .sensor_definitions import SpanPanelCircuitsSensorEntityDescription

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Device types that use "Solar" as the fallback identifier when unnamed,
# matching v1 naming conventions (e.g., "Solar Power", "Solar Produced Energy").
_SOLAR_DEVICE_TYPES: frozenset[str] = frozenset({"pv"})

# Device types that use "EV Charger" as the fallback identifier when unnamed.
_EVSE_DEVICE_TYPES: frozenset[str] = frozenset({"evse"})


def _unnamed_circuit_fallback(circuit: SpanCircuitSnapshot, circuit_id: str) -> str:
    """Return a descriptive identifier for an unnamed circuit.

    PV circuits use "Solar" (matching v1 naming), EVSE circuits use "EV Charger",
    all others use tab-based naming.
    """
    device_type = getattr(circuit, "device_type", "circuit")
    if device_type in _SOLAR_DEVICE_TYPES:
        return "Solar"
    if device_type in _EVSE_DEVICE_TYPES:
        return "EV Charger"
    return construct_circuit_identifier_from_tabs(circuit.tabs, circuit_id)


def _resolve_circuit_identifier(
    circuit: SpanCircuitSnapshot,
    circuit_id: str,
    options: Mapping[str, Any],
) -> str | None:
    """Resolve the circuit identifier respecting user naming preference.

    Returns None when the circuit has no name and user is in friendly-name mode,
    matching v1 behavior where HA handles default naming.
    """
    use_circuit_numbers = options.get(USE_CIRCUIT_NUMBERS, False)

    if use_circuit_numbers:
        return construct_circuit_identifier_from_tabs(circuit.tabs, circuit_id)

    name: str = circuit.name
    if name:
        return name

    return None


def _resolve_circuit_identifier_for_sync(
    circuit: SpanCircuitSnapshot, circuit_id: str
) -> str:
    """Resolve the circuit identifier for name-sync (always panel name, with fallback)."""
    name: str = circuit.name
    if name:
        return name
    return _unnamed_circuit_fallback(circuit, circuit_id)


class SpanCircuitPowerSensor(
    SpanSensorBase[SpanPanelCircuitsSensorEntityDescription, SpanCircuitSnapshot]
):
    """Circuit power/current/breaker-rating sensor with extra state attributes."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPanelCircuitsSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
        circuit_id: str,
        device_info_override: DeviceInfo | None = None,
    ) -> None:
        """Initialize the enhanced circuit power sensor."""
        self.circuit_id = circuit_id
        self.original_key = description.key
        self._is_sub_device = device_info_override is not None

        # Override the description key to use the circuit_id for data lookup
        description_with_circuit = SpanPanelCircuitsSensorEntityDescription(
            key=circuit_id,
            name=description.name,
            native_unit_of_measurement=description.native_unit_of_measurement,
            state_class=description.state_class,
            suggested_display_precision=description.suggested_display_precision,
            device_class=description.device_class,
            value_fn=description.value_fn,
            entity_registry_enabled_default=description.entity_registry_enabled_default,
            entity_registry_visible_default=description.entity_registry_visible_default,
            entity_category=description.entity_category,
        )

        super().__init__(data_coordinator, description_with_circuit, snapshot)

        if device_info_override is not None:
            self._attr_device_info = device_info_override

    # Map original description keys to API keys for unique ID generation
    _API_KEY_MAP: dict[str, str] = {
        "circuit_power": "instantPowerW",
        "circuit_current": "current",
        "circuit_breaker_rating": "breaker_rating",
    }

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
    ) -> str:
        """Generate unique ID for circuit power sensors."""
        api_key = self._API_KEY_MAP.get(self.original_key, self.original_key)
        return construct_circuit_unique_id_for_entry(
            self.coordinator, snapshot, self.circuit_id, api_key, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
    ) -> str | None:
        """Generate friendly name for circuit power sensors based on user preferences.

        Returns None when circuit has no name in friendly-name mode,
        matching v1 behavior where HA handles default naming.
        For sub-device sensors (EVSE), returns just the description name
        since the device name already provides circuit context.
        """
        if self._is_sub_device:
            return str(description.name or "Sensor")

        circuit = snapshot.circuits.get(self.circuit_id)
        if not circuit:
            return construct_unmapped_friendly_name(
                self.circuit_id, str(description.name or "Sensor")
            )

        circuit_identifier = _resolve_circuit_identifier(
            circuit, self.circuit_id, self.coordinator.config_entry.options
        )
        if circuit_identifier is None:
            return None
        return f"{circuit_identifier} {description.name or 'Sensor'}"

    def _generate_panel_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
    ) -> str:
        """Generate panel name for circuit sensors (always uses panel circuit name)."""
        if self._is_sub_device:
            return str(description.name or "Sensor")

        circuit = snapshot.circuits.get(self.circuit_id)
        if not circuit:
            return construct_unmapped_friendly_name(
                self.circuit_id, str(description.name or "Sensor")
            )

        circuit_identifier = _resolve_circuit_identifier_for_sync(
            circuit, self.circuit_id
        )
        return f"{circuit_identifier} {description.name or 'Sensor'}"

    def _construct_entity_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
        existing_entity_id: str | None = None,
    ) -> str | None:
        """Construct explicit entity_id for circuit power sensors."""
        circuit = snapshot.circuits.get(self.circuit_id)
        if not circuit:
            return None
        suffix = get_user_friendly_suffix(
            self._API_KEY_MAP.get(self.original_key, self.original_key)
        )
        return construct_single_circuit_entity_id(
            self.coordinator,
            snapshot,
            "sensor",
            suffix,
            circuit,
            unique_id=self._attr_unique_id if existing_entity_id else None,
        )

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanCircuitSnapshot:
        """Get the data source for the circuit power sensor."""
        circuit = snapshot.circuits.get(self.circuit_id)
        if circuit is None:
            raise ValueError(f"Circuit {self.circuit_id} not found in panel data")
        return circuit

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None

        circuit = self.coordinator.data.circuits.get(self.circuit_id)
        if not circuit:
            return None

        attributes: dict[str, Any] = {}

        # Panel position (tabs)
        tabs_result = construct_tabs_attribute(circuit)
        if tabs_result is not None:
            attributes["tabs"] = tabs_result

        # Voltage derived from tab count
        voltage = construct_voltage_attribute(circuit) or 240
        attributes["voltage"] = voltage

        attributes["always_on"] = circuit.always_on
        attributes["relay_state"] = circuit.relay_state
        attributes["relay_requester"] = circuit.relay_requester
        attributes["shed_priority"] = circuit.priority
        attributes["is_sheddable"] = circuit.is_sheddable

        return attributes


class SpanCircuitEnergySensor(
    SpanEnergySensorBase[SpanPanelCircuitsSensorEntityDescription, SpanCircuitSnapshot]
):
    """Circuit energy sensor with grace period tracking."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPanelCircuitsSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
        circuit_id: str,
        device_info_override: DeviceInfo | None = None,
    ) -> None:
        """Initialize the circuit energy sensor."""
        self.circuit_id = circuit_id
        self.original_key = description.key
        self._is_sub_device = device_info_override is not None

        # Override the description key to use the circuit_id for data lookup
        description_with_circuit = SpanPanelCircuitsSensorEntityDescription(
            key=circuit_id,
            name=description.name,
            native_unit_of_measurement=description.native_unit_of_measurement,
            state_class=description.state_class,
            suggested_display_precision=description.suggested_display_precision,
            device_class=description.device_class,
            value_fn=description.value_fn,
            entity_registry_enabled_default=description.entity_registry_enabled_default,
            entity_registry_visible_default=description.entity_registry_visible_default,
        )

        super().__init__(data_coordinator, description_with_circuit, snapshot)

        if device_info_override is not None:
            self._attr_device_info = device_info_override

    async def async_added_to_hass(self) -> None:
        """Register consumed/produced sensors on the coordinator for net energy lookup."""
        await super().async_added_to_hass()
        energy_type = self._ENERGY_TYPE_MAP.get(self.original_key)
        if energy_type:
            self.coordinator.register_circuit_energy_sensor(
                self.circuit_id, energy_type, self
            )

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
    ) -> str:
        """Generate unique ID for circuit energy sensors."""
        # Map new description keys to original API keys that migration normalized from
        api_key_mapping = {
            "circuit_energy_produced": "producedEnergyWh",
            "circuit_energy_consumed": "consumedEnergyWh",
            "circuit_energy_net": "netEnergyWh",
        }
        api_key = api_key_mapping.get(self.original_key, self.original_key)
        return construct_circuit_unique_id_for_entry(
            self.coordinator, snapshot, self.circuit_id, api_key, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
    ) -> str | None:
        """Generate friendly name for circuit energy sensors based on user preferences.

        Returns None when circuit has no name in friendly-name mode,
        matching v1 behavior where HA handles default naming.
        For sub-device sensors (EVSE), returns just the description name
        since the device name already provides circuit context.
        """
        if self._is_sub_device:
            return str(description.name)

        circuit = snapshot.circuits.get(self.circuit_id)
        if not circuit:
            return f"Circuit {self.circuit_id} {description.name}"

        circuit_identifier = _resolve_circuit_identifier(
            circuit, self.circuit_id, self.coordinator.config_entry.options
        )
        if circuit_identifier is None:
            return None
        return f"{circuit_identifier} {description.name}"

    def _generate_panel_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
    ) -> str:
        """Generate panel name for circuit energy sensors (always uses panel circuit name)."""
        if self._is_sub_device:
            return str(description.name)

        circuit = snapshot.circuits.get(self.circuit_id)
        if not circuit:
            return f"Circuit {self.circuit_id} {description.name}"

        circuit_identifier = _resolve_circuit_identifier_for_sync(
            circuit, self.circuit_id
        )
        return f"{circuit_identifier} {description.name}"

    def _construct_entity_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
        existing_entity_id: str | None = None,
    ) -> str | None:
        """Construct explicit entity_id for circuit energy sensors."""
        circuit = snapshot.circuits.get(self.circuit_id)
        if not circuit:
            return None
        api_key_mapping = {
            "circuit_energy_produced": "producedEnergyWh",
            "circuit_energy_consumed": "consumedEnergyWh",
            "circuit_energy_net": "netEnergyWh",
        }
        api_key = api_key_mapping.get(self.original_key, self.original_key)
        suffix = get_user_friendly_suffix(api_key)
        return construct_single_circuit_entity_id(
            self.coordinator,
            snapshot,
            "sensor",
            suffix,
            circuit,
            unique_id=self._attr_unique_id if existing_entity_id else None,
        )

    # Map original_key to the energy type used for coordinator dip offset tracking
    _ENERGY_TYPE_MAP: dict[str, str] = {
        "circuit_energy_consumed": "consumed",
        "circuit_energy_produced": "produced",
    }

    def _process_raw_value(self, raw_value: float | str | None) -> None:
        """Process raw value, adjusting net energy for dip compensation consistency.

        Consumed/produced sensors apply dip offsets via the base class. The net
        energy sensor reads those offsets from the registered sibling sensors
        so its value stays equal to compensated_consumed - compensated_produced.
        """
        super()._process_raw_value(raw_value)

        if self.original_key == "circuit_energy_net" and isinstance(
            self._attr_native_value, float
        ):
            consumed_offset = self.coordinator.get_circuit_dip_offset(
                self.circuit_id, "consumed"
            )
            produced_offset = self.coordinator.get_circuit_dip_offset(
                self.circuit_id, "produced"
            )
            net_adjustment = consumed_offset - produced_offset
            if net_adjustment:
                self._attr_native_value += net_adjustment

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanCircuitSnapshot:
        """Get the data source for the circuit energy sensor."""
        return snapshot.circuits[self.circuit_id]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes including grace period and circuit info."""
        # Get base grace period attributes
        base_attributes = super().extra_state_attributes or {}
        attributes = dict(base_attributes)

        # Add circuit-specific attributes if we have data
        if self.coordinator.data:
            circuit = self.coordinator.data.circuits.get(self.circuit_id)

            if circuit:
                tabs = construct_tabs_attribute(circuit)
                if tabs is not None:
                    attributes["tabs"] = tabs

                voltage = construct_voltage_attribute(circuit) or 240
                attributes["voltage"] = voltage

        return attributes or None


class SpanUnmappedCircuitSensor(
    SpanSensorBase[SpanPanelCircuitsSensorEntityDescription, SpanCircuitSnapshot]
):
    """Span Panel unmapped circuit sensor entity - native sensors for synthetic calculations."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPanelCircuitsSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
        circuit_id: str,
    ) -> None:
        """Initialize the Span Panel unmapped circuit sensor."""
        self.circuit_id = circuit_id
        # Store the original description key for unique ID and entity ID generation
        self.original_key = description.key

        # Override the description key to use the circuit_id for data lookup
        description_with_circuit = SpanPanelCircuitsSensorEntityDescription(
            key=circuit_id,
            name=description.name,
            native_unit_of_measurement=description.native_unit_of_measurement,
            state_class=description.state_class,
            suggested_display_precision=description.suggested_display_precision,
            device_class=description.device_class,
            value_fn=description.value_fn,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        )

        super().__init__(data_coordinator, description_with_circuit, snapshot)

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
    ) -> str:
        """Generate unique ID for unmapped circuit sensors."""
        return construct_circuit_unique_id_for_entry(
            self.coordinator,
            snapshot,
            self.circuit_id,
            self.original_key,
            self._device_name,
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelCircuitsSensorEntityDescription,
    ) -> str:
        """Generate friendly name for unmapped circuit sensors."""
        tab_number = self.circuit_id.replace("unmapped_tab_", "")
        description_name = str(description.name) if description.name else "Sensor"
        return construct_unmapped_friendly_name(tab_number, description_name)

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanCircuitSnapshot:
        """Get the data source for the unmapped circuit sensor."""
        return snapshot.circuits[self.circuit_id]
