"""Control switches."""

from collections.abc import Mapping
import logging
import time
from typing import Any

from span_panel_api import SpanCircuitSnapshot, SpanPanelSnapshot

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpanPanelConfigEntry
from .const import DOMAIN, USE_CIRCUIT_NUMBERS, CircuitRelayState
from .coordinator import SpanPanelCoordinator
from .entity import SpanPanelEntity
from .helpers import (
    build_switch_unique_id_for_entry,
    construct_circuit_identifier_from_tabs,
    construct_single_circuit_entity_id,
    construct_tabs_attribute,
    construct_voltage_attribute,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Sentinel value to distinguish "never synced" from "circuit name is None"
_NAME_UNSET: object = object()

# Device types that use "Solar" as the fallback identifier when unnamed.
_SOLAR_DEVICE_TYPES: frozenset[str] = frozenset({"pv"})

# How long (seconds) to hold an optimistic state before allowing the coordinator
# to overwrite it.  This prevents the UI from bouncing back to stale state when
# the panel has not yet processed a relay command.
_OPTIMISTIC_HOLD_SECONDS: float = 10.0


def _unnamed_switch_fallback(circuit: SpanCircuitSnapshot, circuit_id: str) -> str:
    """Return a descriptive identifier for an unnamed circuit switch."""
    if getattr(circuit, "device_type", "circuit") in _SOLAR_DEVICE_TYPES:
        return "Solar"
    return construct_circuit_identifier_from_tabs(circuit.tabs, circuit_id)


class SpanPanelCircuitsSwitch(SpanPanelEntity, SwitchEntity):
    """Represent a switch entity."""

    def __init__(
        self,
        coordinator: SpanPanelCoordinator,
        circuit_id: str,
        name: str,
        device_name: str,
    ) -> None:
        """Initialize the values."""
        snapshot: SpanPanelSnapshot = coordinator.data

        circuit = snapshot.circuits.get(circuit_id)
        if not circuit:
            raise ValueError(f"Circuit {circuit_id} not found")

        self._circuit_id: str = circuit_id
        self._device_name = device_name
        self._attr_unique_id = self._construct_switch_unique_id(
            coordinator, snapshot, circuit_id
        )

        self._attr_device_info = self._build_device_info(coordinator, snapshot)

        # Check if entity already exists in registry
        entity_registry = er.async_get(coordinator.hass)
        existing_entity_id = entity_registry.async_get_entity_id(
            "switch", DOMAIN, self._attr_unique_id
        )

        use_circuit_numbers = coordinator.config_entry.options.get(
            USE_CIRCUIT_NUMBERS, False
        )

        if existing_entity_id:
            # Entity exists - use circuit-based name when configured, else panel name
            if use_circuit_numbers:
                circuit_identifier = construct_circuit_identifier_from_tabs(
                    circuit.tabs, circuit_id
                )
                self._attr_name = f"{circuit_identifier} Breaker"
            elif circuit.name:
                self._attr_name = f"{circuit.name} Breaker"
            else:
                fallback = _unnamed_switch_fallback(circuit, circuit_id)
                self._attr_name = f"{fallback} Breaker"

        # Sync the panel friendly name to the entity registry display name
        # so the UI shows e.g. "Air Conditioner Breaker" while the entity_id
        # stays circuit-based (e.g. switch.span_panel_circuit_15_breaker).
        if existing_entity_id and use_circuit_numbers and circuit.name:
            entity_entry = entity_registry.async_get(existing_entity_id)
            if entity_entry:
                expected_name = f"{circuit.name} Breaker"
                if entity_entry.name is None or entity_entry.name == expected_name:
                    entity_registry.async_update_entity(
                        existing_entity_id, name=expected_name
                    )

        if not existing_entity_id:
            # Initial install - use flag-based name for entity_id generation
            if use_circuit_numbers:
                circuit_identifier = construct_circuit_identifier_from_tabs(
                    circuit.tabs, circuit_id
                )
                self._attr_name = f"{circuit_identifier} Breaker"
            elif name:
                self._attr_name = f"{name} Breaker"
            else:
                # v1 behavior: None lets HA handle default naming
                self._attr_name = None

        super().__init__(coordinator)

        # Explicitly set entity_id using construct_single_circuit_entity_id
        # which correctly handles 240V two-tab circuits.
        # Only pass unique_id for existing entities (registry lookup);
        # for new entities pass None to get the constructed default.
        constructed_id = construct_single_circuit_entity_id(
            coordinator,
            snapshot,
            "switch",
            "breaker",
            circuit,
            unique_id=self._attr_unique_id if existing_entity_id else None,
        )
        if constructed_id:
            self.entity_id = constructed_id

        # Optimistic state: set when the user toggles the switch so that
        # coordinator refreshes don't overwrite it until confirmed or timed out.
        self._optimistic_state: bool | None = None
        self._optimistic_set_at: float = 0.0

        self._update_is_on()

        # Store initial circuit name for change detection in auto-sync
        if not existing_entity_id:
            self._previous_circuit_name: str | None | object = _NAME_UNSET
            _LOGGER.info("Switch entity not in registry, will sync on first update")
        else:
            self._previous_circuit_name = circuit.name
            _LOGGER.info(
                "Switch entity exists in registry, previous name set to '%s'",
                circuit.name,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        await super().async_will_remove_from_hass()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        snapshot: SpanPanelSnapshot = self.coordinator.data
        circuit = snapshot.circuits.get(self._circuit_id)
        if circuit:
            current_circuit_name = circuit.name
            use_circuit_numbers = self.coordinator.config_entry.options.get(
                USE_CIRCUIT_NUMBERS, False
            )

            if use_circuit_numbers:
                # Circuit-numbers mode: update registry display name, no reload
                if self.entity_id and current_circuit_name:
                    entity_registry = er.async_get(self.hass)
                    entity_entry = entity_registry.async_get(self.entity_id)
                    if entity_entry:
                        # Compute old expected display BEFORE updating
                        # _previous_circuit_name
                        old_display = (
                            f"{self._previous_circuit_name} Breaker"
                            if isinstance(self._previous_circuit_name, str)
                            else None
                        )
                        new_display = f"{current_circuit_name} Breaker"

                        # User override: registry name differs from both old
                        # and new expected display names
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
                        "First update: syncing entity name to panel name '%s' for switch, requesting reload",
                        current_circuit_name,
                    )
                    self._previous_circuit_name = current_circuit_name
                    self.coordinator.request_reload()
                elif current_circuit_name != self._previous_circuit_name:
                    _LOGGER.info(
                        "Auto-sync detected circuit name change from '%s' to '%s' for "
                        "switch, requesting integration reload",
                        self._previous_circuit_name,
                        current_circuit_name,
                    )
                    self._previous_circuit_name = current_circuit_name
                    self.coordinator.request_reload()

        self._update_is_on()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return entity availability.

        Switches become unavailable when panel is offline since they can't control circuits.
        """
        if getattr(self.coordinator, "panel_offline", False):
            return False
        return super().available

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return panel position attributes for this circuit."""
        if not self.coordinator.data:
            return None

        circuit = self.coordinator.data.circuits.get(self._circuit_id)
        if not circuit:
            return None

        attributes: dict[str, Any] = {}

        tabs_result = construct_tabs_attribute(circuit)
        if tabs_result is not None:
            attributes["tabs"] = tabs_result

        voltage = construct_voltage_attribute(circuit) or 240
        attributes["voltage"] = voltage

        return attributes or None

    def _update_is_on(self) -> None:
        """Update the is_on state based on the circuit state.

        When an optimistic state is active (user recently toggled the switch),
        we keep using it until the panel confirms the expected state or the
        hold period expires.  This eliminates the visible bounce caused by
        a coordinator refresh returning stale data before the relay settles.
        """
        snapshot: SpanPanelSnapshot = self.coordinator.data
        circuit = snapshot.circuits.get(self._circuit_id)
        if not circuit:
            self._optimistic_state = None
            self._attr_is_on = None
            return

        actual_is_on = circuit.relay_state == CircuitRelayState.CLOSED.name

        if self._optimistic_state is not None:
            elapsed = time.monotonic() - self._optimistic_set_at
            if actual_is_on == self._optimistic_state:
                # Panel confirmed the expected state — clear the hold.
                self._optimistic_state = None
                self._attr_is_on = actual_is_on
            elif elapsed < _OPTIMISTIC_HOLD_SECONDS:
                # Still within the hold window — keep the optimistic value.
                self._attr_is_on = self._optimistic_state
            else:
                # Hold expired and the panel never confirmed — accept reality.
                _LOGGER.debug(
                    "Optimistic hold expired for circuit %s; expected %s, actual %s",
                    self._circuit_id,
                    self._optimistic_state,
                    actual_is_on,
                )
                self._optimistic_state = None
                self._attr_is_on = actual_is_on
        else:
            self._attr_is_on = actual_is_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.hass.create_task(self.async_turn_on(**kwargs))

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.hass.create_task(self.async_turn_off(**kwargs))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        client = self.coordinator.client
        if not hasattr(client, "set_circuit_relay"):
            _LOGGER.warning("Client does not support relay control")
            return

        await client.set_circuit_relay(self._circuit_id, "CLOSED")
        self._set_optimistic_state(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        client = self.coordinator.client
        if not hasattr(client, "set_circuit_relay"):
            _LOGGER.warning("Client does not support relay control")
            return

        await client.set_circuit_relay(self._circuit_id, "OPEN")
        self._set_optimistic_state(False)
        await self.coordinator.async_request_refresh()

    def _set_optimistic_state(self, target: bool) -> None:
        """Set the optimistic state and immediately push it to HA."""
        self._optimistic_state = target
        self._optimistic_set_at = time.monotonic()
        self._attr_is_on = target
        if self.hass is not None:
            self.async_write_ha_state()

    def _construct_switch_unique_id(
        self,
        coordinator: SpanPanelCoordinator,
        snapshot: SpanPanelSnapshot,
        circuit_id: str,
    ) -> str:
        """Construct unique ID for switch entities."""
        return build_switch_unique_id_for_entry(
            coordinator, snapshot, circuit_id, self._device_name
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SpanPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform."""

    coordinator = config_entry.runtime_data.coordinator
    snapshot: SpanPanelSnapshot = coordinator.data

    # Get device name from config entry data
    _device_name = config_entry.data.get("device_name", config_entry.title)

    entities: list[SpanPanelCircuitsSwitch] = []

    for circuit_id, circuit_data in snapshot.circuits.items():
        if not circuit_data.is_user_controllable:
            continue
        # PV/EVSE circuits only get switches if they have a physical breaker
        # (relative_position == "DOWNSTREAM" means connected at a breaker slot)
        if (
            circuit_data.device_type in ("pv", "evse")
            and circuit_data.relative_position != "DOWNSTREAM"
        ):
            continue
        entities.append(
            SpanPanelCircuitsSwitch(
                coordinator, circuit_id, circuit_data.name, _device_name
            )
        )

    async_add_entities(entities)
