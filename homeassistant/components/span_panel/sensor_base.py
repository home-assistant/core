"""Base sensor classes for Span Panel integration."""

# pylint: disable=hass-enforce-class-module

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
from typing import Any, Self, cast

from span_panel_api import SpanPanelSnapshot

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, ENABLE_ENERGY_DIP_COMPENSATION, USE_CIRCUIT_NUMBERS
from .coordinator import SpanPanelCoordinator
from .entity import SpanPanelEntity
from .options import ENERGY_REPORTING_GRACE_PERIOD

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Sentinel value to distinguish "never synced" from "circuit name is None"
_NAME_UNSET: object = object()

# Keys from Span energy sensors' extra_state_attributes that we omit from the recorder
# (SpanEnergySensorBase: panel-wide and circuit energy entities). High-churn grace/dip
# diagnostics dominated DB growth (#197). tabs and voltage are merged in by circuit
# subclasses; they stay on the live entity for Developer tools and automations.
_ENERGY_SENSOR_UNRECORDED_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "energy_offset",
        "grace_period_remaining",
        "last_dip_delta",
        "last_valid_changed",
        "last_valid_state",
        "tabs",
        "using_grace_period",
        "voltage",
    }
)


def _parse_numeric_state(state: State | None) -> tuple[float | None, datetime | None]:
    """Extract a numeric value and naive timestamp from a restored HA state.

    Returns (None, None) when the state is unknown/unavailable or not numeric.
    """

    if state is None:
        return None, None

    if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, None):
        return None, None

    try:
        value = float(state.state)
    except TypeError, ValueError:
        return None, None

    # Normalize last_changed to naive datetime to match existing tracking
    last_changed = (
        state.last_changed.replace(tzinfo=None) if state.last_changed else None
    )
    return value, last_changed


class SpanSensorBase[T: SensorEntityDescription, D](SpanPanelEntity, SensorEntity, ABC):
    """Abstract base class for Span Panel sensors with overridable methods."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: T,
        snapshot: SpanPanelSnapshot,
    ) -> None:
        """Initialize Span Panel Sensor base entity."""
        super().__init__(data_coordinator, context=description)
        self.entity_description = description

        if hasattr(description, "device_class"):
            self._attr_device_class = description.device_class

        if hasattr(description, "options") and description.options:
            self._attr_options = list(description.options)

        # Get device name from config entry data
        self._device_name = data_coordinator.config_entry.data.get(
            "device_name", data_coordinator.config_entry.title
        )

        self._attr_device_info = self._build_device_info(data_coordinator, snapshot)

        # Check if entity already exists in registry for name sync
        if snapshot.serial_number and description.key:
            self._attr_unique_id = self._generate_unique_id(snapshot, description)

            # Entities with translation_key get their name from translations/en.json.
            # Only set _attr_name for entities without translation_key (e.g.,
            # circuit sensors whose names include the dynamic circuit name).
            if not getattr(description, "translation_key", None):
                entity_registry = er.async_get(data_coordinator.hass)
                existing_entity_id = entity_registry.async_get_entity_id(
                    "sensor", DOMAIN, self._attr_unique_id
                )

                use_circuit_numbers = data_coordinator.config_entry.options.get(
                    USE_CIRCUIT_NUMBERS, False
                )

                if existing_entity_id:
                    if use_circuit_numbers:
                        # Circuit-numbers mode: keep circuit-based name for entity_id stability
                        self._attr_name = self._generate_friendly_name(
                            snapshot, description
                        )
                    else:
                        # Friendly-names mode: use panel name for sync
                        self._attr_name = self._generate_panel_name(
                            snapshot, description
                        )
                else:
                    # Initial install - use flag-based name
                    self._attr_name = self._generate_friendly_name(
                        snapshot, description
                    )

                # Sync panel friendly name to registry display name in
                # circuit-numbers mode so the UI shows e.g.
                # "Kitchen Power" while entity_id stays circuit-based.
                if existing_entity_id and use_circuit_numbers:
                    self._sync_friendly_name_to_registry(
                        snapshot, description, entity_registry, existing_entity_id
                    )

                # Wire explicit entity_id via subclass helper
                entity_id = self._construct_entity_id(
                    snapshot, description, existing_entity_id
                )
                if entity_id:
                    self.entity_id = entity_id
        else:
            # Fallback for entities without unique_id
            self._attr_name = self._generate_friendly_name(snapshot, description)

        # Set entity registry defaults if they exist in the description
        if hasattr(description, "entity_registry_enabled_default"):
            self._attr_entity_registry_enabled_default = (
                description.entity_registry_enabled_default
            )
        if hasattr(description, "entity_registry_visible_default"):
            self._attr_entity_registry_visible_default = (
                description.entity_registry_visible_default
            )

        # Initialize name sync tracking
        # Use sentinel to distinguish "never synced" from "circuit name is None"
        if snapshot.serial_number and description.key and self._attr_unique_id:
            entity_registry = er.async_get(data_coordinator.hass)
            existing_entity_id = entity_registry.async_get_entity_id(
                "sensor", DOMAIN, self._attr_unique_id
            )
            if not existing_entity_id:
                self._previous_circuit_name: str | None | object = _NAME_UNSET
            # Entity exists, get current circuit name for comparison
            elif hasattr(self, "circuit_id"):
                circuit = snapshot.circuits.get(getattr(self, "circuit_id", ""))
                self._previous_circuit_name = circuit.name if circuit else None
            else:
                self._previous_circuit_name = None
        else:
            self._previous_circuit_name = _NAME_UNSET

        # Use standard coordinator pattern - entities will update automatically
        # when coordinator data changes

    @abstractmethod
    def _generate_unique_id(self, snapshot: SpanPanelSnapshot, description: T) -> str:
        """Generate unique ID for the sensor.

        Subclasses must implement this to define their unique ID strategy.

        Args:
            snapshot: The panel snapshot data
            description: The sensor description

        Returns:
            Unique ID string

        """

    @abstractmethod
    def _generate_friendly_name(
        self, snapshot: SpanPanelSnapshot, description: T
    ) -> str | None:
        """Generate friendly name for the sensor.

        Subclasses must implement this to define their naming strategy.

        Args:
            snapshot: The panel snapshot data
            description: The sensor description

        Returns:
            Friendly name string, or None to let HA use default behavior

        """

    def _generate_panel_name(
        self, snapshot: SpanPanelSnapshot, description: T
    ) -> str | None:
        """Generate panel name for the sensor (always uses panel circuit name).

        This method is used for name sync - it always uses the panel circuit name
        regardless of user preferences.

        Args:
            snapshot: The panel snapshot data
            description: The sensor description

        Returns:
            Panel name string

        """
        # This should be implemented by subclasses that need name sync
        # For now, fall back to friendly name
        return self._generate_friendly_name(snapshot, description)

    def _sync_friendly_name_to_registry(
        self,
        snapshot: SpanPanelSnapshot,
        description: T,
        entity_registry: er.EntityRegistry,
        existing_entity_id: str,
    ) -> None:
        """Sync panel circuit name to registry display name in circuit-numbers mode."""
        circuit = snapshot.circuits.get(getattr(self, "circuit_id", ""))
        if not (circuit and circuit.name):
            return
        entity_entry = entity_registry.async_get(existing_entity_id)
        if not entity_entry:
            return
        description_suffix = str(getattr(description, "name", None) or "Sensor")
        expected_name = f"{circuit.name} {description_suffix}"
        if entity_entry.name is None or entity_entry.name == expected_name:
            entity_registry.async_update_entity(existing_entity_id, name=expected_name)

    def _construct_entity_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: T,
        existing_entity_id: str | None = None,
    ) -> str | None:
        """Construct explicit entity_id for the sensor.

        Subclasses may override to use entity_id helpers from helpers.py.
        Returns None to let HA auto-generate from _attr_name.

        Args:
            snapshot: The panel snapshot data
            description: The sensor description
            existing_entity_id: The existing entity_id from registry, or None for new entities
        """
        return None

    def _sync_circuit_name(self) -> None:
        """Sync circuit name changes: registry display in circuit-numbers mode, reload in friendly-names mode."""
        if not (
            hasattr(self, "circuit_id") and hasattr(self.coordinator.data, "circuits")
        ):
            return

        circuit = self.coordinator.data.circuits.get(getattr(self, "circuit_id", ""))
        if not circuit:
            return

        current_circuit_name = circuit.name
        use_circuit_numbers = self.coordinator.config_entry.options.get(
            USE_CIRCUIT_NUMBERS, False
        )

        if use_circuit_numbers:
            # Circuit-numbers mode: update registry display name, no reload
            if self.entity_id:
                entity_registry = er.async_get(self.hass)
                entity_entry = entity_registry.async_get(self.entity_id)
                if entity_entry:
                    description_suffix = str(
                        getattr(self.entity_description, "name", None) or "Sensor"
                    )
                    old_display = (
                        f"{self._previous_circuit_name} {description_suffix}"
                        if isinstance(self._previous_circuit_name, str)
                        else None
                    )
                    new_display = f"{current_circuit_name} {description_suffix}"

                    user_has_override = (
                        entity_entry.name is not None
                        and entity_entry.name not in {old_display, new_display}
                    )

                    if not user_has_override and (
                        self._previous_circuit_name is _NAME_UNSET
                        or current_circuit_name != self._previous_circuit_name
                    ):
                        entity_registry.async_update_entity(
                            self.entity_id, name=new_display
                        )
            self._previous_circuit_name = current_circuit_name
        else:
            # Friendly-names mode: existing reload behavior
            user_has_override = False
            if self.entity_id:
                entity_registry = er.async_get(self.hass)
                entity_entry = entity_registry.async_get(self.entity_id)
                if entity_entry and entity_entry.name:
                    user_has_override = True

            if user_has_override:
                self._previous_circuit_name = current_circuit_name
            elif self._previous_circuit_name is _NAME_UNSET:
                _LOGGER.info(
                    "First update: syncing sensor name to panel name '%s', requesting reload",
                    current_circuit_name,
                )
                self._previous_circuit_name = current_circuit_name
                self.coordinator.request_reload()
            elif current_circuit_name != self._previous_circuit_name:
                _LOGGER.info(
                    "Auto-sync detected circuit name change from '%s' to '%s' for sensor, requesting integration reload",
                    self._previous_circuit_name,
                    current_circuit_name,
                )
                self._previous_circuit_name = current_circuit_name
                self.coordinator.request_reload()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_circuit_name()
        self._update_native_value()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return entity availability.

        Keep entities available during a panel_offline condition so sensors can show
        their grace period state (last_valid_state) or None when grace period expires.
        """
        try:
            if getattr(self.coordinator, "panel_offline", False):
                return True
        except AttributeError as err:
            # If coordinator is missing expected attribute, log and fall back
            _LOGGER.debug("Availability check: missing coordinator attribute: %s", err)
        except Exception as err:  # noqa: BLE001  # pragma: no cover - defensive
            # Any unexpected error shouldn't crash the availability check
            _LOGGER.debug("Availability check: unexpected error: %s", err)
        return super().available

    @property
    def _expects_numeric(self) -> bool:
        """Return True if HA expects this sensor to have a numeric value.

        HA raises ValueError when a sensor with a numeric device_class,
        state_class, or native_unit_of_measurement reports a string state
        like STATE_UNKNOWN.  These sensors must use None instead.
        """
        if getattr(self.entity_description, "state_class", None) is not None:
            return True
        if (
            getattr(self.entity_description, "native_unit_of_measurement", None)
            is not None
        ):
            return True
        dc = getattr(self.entity_description, "device_class", None)
        if dc is not None and dc != SensorDeviceClass.ENUM:
            return True
        return False

    def _unknown_value(self) -> StateType:
        """Return the appropriate 'unknown' value for this sensor."""
        return None if self._expects_numeric else STATE_UNKNOWN

    def _update_native_value(self) -> None:
        """Update the native value of the sensor."""
        if self.coordinator.panel_offline:
            self._handle_offline_state()
            return

        self._handle_online_state()

    def _handle_offline_state(self) -> None:
        """Handle sensor state when panel is offline."""
        _LOGGER.debug(
            "STATUS_SENSOR_DEBUG: Panel is offline for %s",
            self.entity_id or self._attr_unique_id,
        )

        device_class = getattr(self.entity_description, "device_class", None)
        if device_class == SensorDeviceClass.POWER:
            self._attr_native_value = 0.0
        elif device_class == SensorDeviceClass.ENERGY:
            self._attr_native_value = None
        else:
            self._attr_native_value = self._unknown_value()

    def _handle_online_state(self) -> None:
        """Handle sensor state when panel is online."""
        value_function: Callable[[D], float | int | str | None] | None = getattr(
            self.entity_description, "value_fn", None
        )
        if value_function is None:
            _LOGGER.debug(
                "STATUS_SENSOR_DEBUG: No value_function for %s",
                self.entity_id or self._attr_unique_id,
            )
            self._attr_native_value = self._unknown_value()
            return

        try:
            data_source: D = self.get_data_source(self.coordinator.data)
            self._log_debug_info(data_source)
            raw_value: float | int | str | None = value_function(data_source)
            self._process_raw_value(raw_value)
        except (AttributeError, KeyError, IndexError) as err:
            _LOGGER.debug(
                "Value lookup failed for %s (%s): %s",
                self.entity_id or self._attr_unique_id,
                getattr(self.entity_description, "key", "?"),
                err,
            )
            self._attr_native_value = self._unknown_value()
        except Exception as err:  # noqa: BLE001  # pragma: no cover - defensive
            # Avoid noisy stack traces from value functions; fall back to unknown
            _LOGGER.warning(
                "Value function failed for %s (%s); reporting unknown",
                self.entity_id or self._attr_unique_id,
                err,
            )
            self._attr_native_value = self._unknown_value()

    def _log_debug_info(self, data_source: D) -> None:
        """Log debug information for circuit sensors."""
        # Only do debug logging if we have valid data and the panel is online
        if (
            not self.coordinator.panel_offline
            and hasattr(self, "id")
            and hasattr(data_source, "instant_power_w")
        ):
            circuit_id = getattr(self, "id", STATE_UNKNOWN)
            instant_power = getattr(data_source, "instant_power_w", None)
            description_key = getattr(self.entity_description, "key", STATE_UNKNOWN)
            _LOGGER.debug(
                "CIRCUIT_POWER_DEBUG: Circuit %s, sensor %s, instant_power=%s, data_source type=%s",
                circuit_id,
                description_key,
                instant_power,
                type(data_source).__name__,
            )

    def _process_raw_value(self, raw_value: float | str | None) -> None:
        """Process the raw value from the value function."""
        if raw_value is None:
            self._attr_native_value = self._unknown_value()
        elif isinstance(raw_value, float | int):
            self._attr_native_value = float(raw_value)
        else:
            str_value = str(raw_value)
            # For enum sensors, ensure the value is in the options list before
            # setting it — HA raises ValueError if the state is not in options.
            # Options are built dynamically from observed MQTT values.
            # Values are normalized to lowercase to satisfy HA's translation
            # key requirement ([a-z0-9-_]+). HA uses the state value directly
            # as the translation key lookup.
            if self._attr_device_class is SensorDeviceClass.ENUM:
                str_value = str_value.lower()
                if not hasattr(self, "_attr_options") or self._attr_options is None:
                    self._attr_options = []
                if str_value not in self._attr_options:
                    self._attr_options.append(str_value)
                    _LOGGER.debug(
                        "Added enum option '%s' for %s",
                        str_value,
                        self.entity_id or self._attr_unique_id,
                    )
            self._attr_native_value = str_value

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> D:
        """Get the data source for the sensor."""
        raise NotImplementedError("Subclasses must implement this method")


@dataclass
class SpanEnergyExtraStoredData(ExtraStoredData):
    """Extra stored data for Span energy sensors with grace period tracking.

    This data is persisted across Home Assistant restarts to maintain
    grace period state for energy sensors, preventing statistics spikes
    when the panel is offline at startup.
    """

    native_value: float | None
    native_unit_of_measurement: str | None
    last_valid_state: float | None
    last_valid_changed: str | None  # ISO format datetime string
    energy_offset: float | None = None
    last_panel_reading: float | None = None
    last_dip_delta: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {
            "native_value": self.native_value,
            "native_unit_of_measurement": self.native_unit_of_measurement,
            "last_valid_state": self.last_valid_state,
            "last_valid_changed": self.last_valid_changed,
            "energy_offset": self.energy_offset,
            "last_panel_reading": self.last_panel_reading,
            "last_dip_delta": self.last_dip_delta,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize extra stored data from a dict.

        Args:
            restored: Dictionary containing the stored data

        Returns:
            SpanEnergyExtraStoredData instance or None if restoration fails

        """
        try:
            return cls(
                native_value=restored.get("native_value"),
                native_unit_of_measurement=restored.get("native_unit_of_measurement"),
                last_valid_state=restored.get("last_valid_state"),
                last_valid_changed=restored.get("last_valid_changed"),
                energy_offset=restored.get("energy_offset"),
                last_panel_reading=restored.get("last_panel_reading"),
                last_dip_delta=restored.get("last_dip_delta"),
            )
        except AttributeError, KeyError, TypeError:
            return None


class SpanEnergySensorBase[T: SensorEntityDescription, D](
    SpanSensorBase[T, D], RestoreSensor, ABC
):
    """Base class for energy sensors that includes grace period tracking.

    This class extends SpanSensorBase with:
    - Grace period tracking for offline scenarios
    - State restoration across HA restarts via RestoreSensor mixin
    - Automatic persistence of last_valid_state and last_valid_changed

    High-churn diagnostic attributes are listed in ``extra_state_attributes`` for
    the UI but omitted from recorder history via ``_unrecorded_attributes`` so the
    database is not flooded with unique attribute blobs on every energy update.
    """

    _unrecorded_attributes = _ENERGY_SENSOR_UNRECORDED_ATTRIBUTES

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: T,
        snapshot: SpanPanelSnapshot,
    ) -> None:
        """Initialize the energy sensor with grace period tracking."""
        super().__init__(data_coordinator, description, snapshot)
        self._last_valid_state: float | None = None
        self._last_valid_changed: datetime | None = None
        self._grace_period_minutes = data_coordinator.config_entry.options.get(
            ENERGY_REPORTING_GRACE_PERIOD, 15
        )
        # Track if we've restored data (used for logging)
        self._restored_from_storage: bool = False

        # Energy dip compensation state
        self._energy_offset: float = 0.0
        self._last_panel_reading: float | None = None
        self._last_dip_delta: float | None = None
        self._is_total_increasing: bool = (
            getattr(description, "state_class", None)
            == SensorStateClass.TOTAL_INCREASING
        )
        self._dip_compensation_enabled: bool = (
            data_coordinator.config_entry.options.get(
                ENABLE_ENERGY_DIP_COMPENSATION, False
            )
        )

    @property
    def energy_offset(self) -> float:
        """Return the cumulative dip compensation offset."""
        return self._energy_offset

    def _process_raw_value(self, raw_value: float | str | None) -> None:
        """Process the raw value with energy dip compensation for TOTAL_INCREASING sensors."""
        if (
            self._dip_compensation_enabled
            and self._is_total_increasing
            and isinstance(raw_value, float | int)
        ):
            raw_float = float(raw_value)
            if (
                self._last_panel_reading is not None
                and self._last_panel_reading - raw_float >= 1.0
            ):
                dip = self._last_panel_reading - raw_float
                self._energy_offset += dip
                self._last_dip_delta = dip
                self.coordinator.report_energy_dip(
                    self.entity_id or self._attr_unique_id or "unknown",
                    dip,
                    self._energy_offset,
                )
            self._last_panel_reading = raw_float
            super()._process_raw_value(raw_float + self._energy_offset)
        else:
            super()._process_raw_value(raw_value)

    async def async_added_to_hass(self) -> None:
        """Restore grace period state when entity is added to Home Assistant.

        This method is called when the entity is added to HA, which happens
        during startup or when the integration is reloaded. We use this
        opportunity to restore the grace period tracking state from storage.
        """
        await super().async_added_to_hass()

        # Try to restore the grace period state from storage
        if (last_extra_data := await self.async_get_last_extra_data()) is not None:
            restored = SpanEnergyExtraStoredData.from_dict(last_extra_data.as_dict())
            if restored:
                # Restore last_valid_state
                if restored.last_valid_state is not None:
                    self._last_valid_state = restored.last_valid_state

                # Restore last_valid_changed timestamp
                if restored.last_valid_changed is not None:
                    try:
                        self._last_valid_changed = datetime.fromisoformat(
                            restored.last_valid_changed
                        )
                        self._restored_from_storage = True
                        _LOGGER.debug(
                            "Restored grace period state for %s: "
                            "last_valid_state=%s, last_valid_changed=%s",
                            self.entity_id or self._attr_unique_id,
                            self._last_valid_state,
                            self._last_valid_changed,
                        )
                    except (ValueError, TypeError) as e:
                        _LOGGER.warning(
                            "Failed to parse restored last_valid_changed for %s: %s",
                            self.entity_id or self._attr_unique_id,
                            e,
                        )

                # Restore energy dip compensation state (only when enabled)
                if self._dip_compensation_enabled and self._is_total_increasing:
                    if restored.energy_offset is not None:
                        self._energy_offset = restored.energy_offset
                    if restored.last_panel_reading is not None:
                        self._last_panel_reading = restored.last_panel_reading
                    if restored.last_dip_delta is not None:
                        self._last_dip_delta = restored.last_dip_delta
                    _LOGGER.debug(
                        "Restored energy dip compensation for %s: "
                        "offset=%s, last_reading=%s, last_dip=%s",
                        self.entity_id or self._attr_unique_id,
                        self._energy_offset,
                        self._last_panel_reading,
                        self._last_dip_delta,
                    )

        # Seed grace period tracking from the last stored HA state when extra data
        # is missing (e.g., after first install or early offline event).
        await self._initialize_grace_period_from_last_state()

    async def _initialize_grace_period_from_last_state(self) -> None:
        """Seed grace tracking from HA's last stored state when extra data is missing."""

        if self._last_valid_state is not None:
            return

        try:
            last_state = await self.async_get_last_state()
        except Exception as err:  # noqa: BLE001  # pragma: no cover - defensive
            _LOGGER.debug(
                "Grace period restore: failed to fetch last state for %s: %s",
                self.entity_id or self._attr_unique_id,
                err,
            )
            return

        restored_value, restored_changed = _parse_numeric_state(last_state)
        if restored_value is None:
            return

        self._last_valid_state = restored_value
        self._last_valid_changed = restored_changed or datetime.now()
        self._restored_from_storage = True
        _LOGGER.debug(
            "Grace period initialized from last state for %s: value=%s, changed=%s",
            self.entity_id or self._attr_unique_id,
            self._last_valid_state,
            self._last_valid_changed,
        )

    @property
    def extra_restore_state_data(self) -> SensorExtraStoredData:
        """Return sensor-specific state data to be restored.

        This data is automatically saved by Home Assistant when the
        integration is unloaded or HA shuts down, and restored when
        the entity is added back to HA.
        """
        return cast(
            SensorExtraStoredData,
            SpanEnergyExtraStoredData(
                native_value=(
                    float(self._attr_native_value)
                    if isinstance(self._attr_native_value, int | float)
                    else None
                ),
                native_unit_of_measurement=self.native_unit_of_measurement,
                last_valid_state=self._last_valid_state,
                last_valid_changed=(
                    self._last_valid_changed.isoformat()
                    if self._last_valid_changed
                    else None
                ),
                energy_offset=self._energy_offset or None,
                last_panel_reading=self._last_panel_reading,
                last_dip_delta=self._last_dip_delta,
            ),
        )

    def _update_native_value(self) -> None:
        """Update the native value with grace period logic for energy sensors."""
        if self.coordinator.panel_offline:
            # Use grace period logic when offline
            self._handle_offline_grace_period()
            return

        # Panel is online - use normal update logic from parent class
        super()._update_native_value()

        self._track_valid_state(self._attr_native_value)

    def _track_valid_state(self, value: StateType | date | Decimal | None) -> None:
        """Update last valid state tracking when a numeric value is available."""
        if value is not None and isinstance(value, int | float | Decimal):
            self._last_valid_state = float(value)
            self._last_valid_changed = datetime.now()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator with grace period tracking."""
        self._sync_circuit_name()

        # Update grace period from options in case it changed
        self._grace_period_minutes = self.coordinator.config_entry.options.get(
            ENERGY_REPORTING_GRACE_PERIOD, 15
        )

        # Update dip compensation flag from options in case it changed
        self._dip_compensation_enabled = self.coordinator.config_entry.options.get(
            ENABLE_ENERGY_DIP_COMPENSATION, False
        )

        # Use the overridden _update_native_value method which handles grace period
        self._update_native_value()

        # Call the parent's parent class coordinator update to avoid the intermediate parent's logic
        super(SpanSensorBase, self)._handle_coordinator_update()

    def _handle_offline_grace_period(self) -> None:
        """Handle grace period logic when panel is offline."""
        # If we don't yet have a tracked valid state, fall back to the current
        # native value (e.g., restored state) to avoid returning None during a
        # brief offline period immediately after startup.
        if self._last_valid_state is None and isinstance(
            self._attr_native_value, int | float
        ):
            self._last_valid_state = float(self._attr_native_value)
            self._last_valid_changed = self._last_valid_changed or datetime.now()

        if self._last_valid_state is None:
            # No previous valid state, set to None (HA reports unknown)
            self._attr_native_value = None
            return

        if self._last_valid_changed is None:
            self._last_valid_changed = datetime.now()

        grace_minutes = self._coerce_grace_period_minutes()

        try:
            time_since_last_valid = datetime.now() - self._last_valid_changed
            grace_period_duration = timedelta(minutes=grace_minutes)
        except Exception as err:  # noqa: BLE001  # pragma: no cover - defensive
            _LOGGER.debug("Grace period calculation failed: %s", err)
            self._attr_native_value = self._last_valid_state
            return

        if time_since_last_valid <= grace_period_duration:
            # Still within grace period - use last valid state
            self._attr_native_value = self._last_valid_state
        else:
            # Grace period expired - set to None (makes sensor unknown)
            self._attr_native_value = None

    def _coerce_grace_period_minutes(self) -> int:
        """Ensure grace period minutes is a non-negative integer."""

        try:
            minutes = int(self._grace_period_minutes)
        except TypeError, ValueError:
            minutes = 15
            self._grace_period_minutes = minutes

        if minutes < 0:
            minutes = 0
            self._grace_period_minutes = minutes

        return minutes

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes including grace period info."""
        attributes = {}

        # Always show grace period information if we have valid tracking data
        if self._last_valid_changed is not None:
            if self._last_valid_state is not None:
                attributes["last_valid_state"] = str(self._last_valid_state)
            attributes["last_valid_changed"] = self._last_valid_changed.isoformat()

            # Calculate grace period remaining
            grace_minutes = self._coerce_grace_period_minutes()
            if grace_minutes > 0:
                time_since_last_valid = datetime.now() - self._last_valid_changed
                grace_period_duration = timedelta(minutes=grace_minutes)
                remaining_seconds = (
                    grace_period_duration - time_since_last_valid
                ).total_seconds()
                remaining_minutes = max(0, int(remaining_seconds / 60))
                attributes["grace_period_remaining"] = str(remaining_minutes)

                # Indicate if we're currently using grace period
                panel_offline = getattr(self.coordinator, "panel_offline", False)
                if panel_offline and remaining_seconds > 0:
                    attributes["using_grace_period"] = "True"

        # Energy dip compensation attributes (only when enabled and meaningful)
        if self._dip_compensation_enabled and self._is_total_increasing:
            if self._energy_offset > 0:
                attributes["energy_offset"] = str(round(self._energy_offset, 1))
            if self._last_dip_delta is not None:
                attributes["last_dip_delta"] = str(round(self._last_dip_delta, 1))

        return attributes or None
