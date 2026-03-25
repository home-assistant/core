"""Select entity for the Span Panel."""

from collections.abc import Callable, Mapping
import logging
from typing import Any, Final

from span_panel_api import SpanCircuitSnapshot, SpanPanelSnapshot
from span_panel_api.exceptions import SpanPanelServerError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpanPanelConfigEntry
from .const import DOMAIN, USE_CIRCUIT_NUMBERS, CircuitPriority
from .coordinator import SpanPanelCoordinator
from .entity import SpanPanelEntity
from .helpers import (
    async_create_span_notification,
    build_select_unique_id_for_entry,
    construct_circuit_identifier_from_tabs,
    construct_single_circuit_entity_id,
    construct_tabs_attribute,
    construct_voltage_attribute,
)

# Device types that use "Solar" as the fallback identifier when unnamed.
_SOLAR_DEVICE_TYPES: frozenset[str] = frozenset({"pv"})


def _unnamed_select_fallback(circuit: SpanCircuitSnapshot, circuit_id: str) -> str:
    """Return a descriptive identifier for an unnamed circuit select."""
    if getattr(circuit, "device_type", "circuit") in _SOLAR_DEVICE_TYPES:
        return "Solar"
    return construct_circuit_identifier_from_tabs(circuit.tabs, circuit_id)


_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Sentinel value to distinguish "never synced" from "circuit name is None"
_NAME_UNSET: object = object()


class SpanPanelSelectEntityDescriptionWrapper:
    """Wrapper class for Span Panel Select entities."""

    # The wrapper is required because the SelectEntityDescription is frozen
    # and we need to pass in the entity_description to the constructor
    # Using keyword arguments gives a warning about unexpected arguments
    # pylint: disable=too-few-public-methods

    def __init__(
        self,
        key: str,
        name: str,
        options_fn: Callable[[SpanCircuitSnapshot], list[str]] = lambda _: [],
        current_option_fn: Callable[[SpanCircuitSnapshot], str | None] = lambda _: None,
        select_option_fn: Callable[[SpanCircuitSnapshot, str], None] | None = None,
    ) -> None:
        """Initialize the select entity description wrapper."""
        self.entity_description = SelectEntityDescription(
            key=key,
            name=name,
            translation_key=key,
            entity_category=EntityCategory.CONFIG,
        )
        self.options_fn = options_fn
        self.current_option_fn = current_option_fn
        self.select_option_fn = select_option_fn


CIRCUIT_PRIORITY_DESCRIPTION: Final = SpanPanelSelectEntityDescriptionWrapper(
    key="circuit_priority",
    name="Circuit Priority",
    options_fn=lambda _: [
        e.value for e in CircuitPriority if e != CircuitPriority.UNKNOWN
    ],
    current_option_fn=lambda circuit: CircuitPriority[circuit.priority].value,
)


class SpanPanelCircuitsSelect(SpanPanelEntity, SelectEntity):
    """Represent a select entity for Span Panel circuits."""

    def __init__(
        self,
        coordinator: SpanPanelCoordinator,
        description: SpanPanelSelectEntityDescriptionWrapper,
        circuit_id: str,
        name: str,
        device_name: str,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        snapshot: SpanPanelSnapshot = coordinator.data

        circuit = snapshot.circuits.get(circuit_id)
        if not circuit:
            raise ValueError(f"Circuit {circuit_id} not found")

        self.entity_description = description.entity_description
        self.description_wrapper = description
        self.id = circuit_id
        self._device_name = device_name

        self._attr_unique_id = self._construct_select_unique_id(
            coordinator, snapshot, self.id
        )

        self._attr_device_info = self._build_device_info(coordinator, snapshot)

        # Check if entity already exists in registry
        entity_registry = er.async_get(coordinator.hass)
        existing_entity_id = entity_registry.async_get_entity_id(
            "select", DOMAIN, self._attr_unique_id
        )

        use_circuit_numbers = coordinator.config_entry.options.get(
            USE_CIRCUIT_NUMBERS, False
        )

        desc_name = description.entity_description.name
        if existing_entity_id:
            # Entity exists - use circuit-based name when configured, else panel name
            if use_circuit_numbers:
                circuit_identifier = construct_circuit_identifier_from_tabs(
                    circuit.tabs, circuit_id
                )
                self._attr_name = f"{circuit_identifier} {desc_name}"
            elif circuit.name:
                self._attr_name = f"{circuit.name} {desc_name}"
            else:
                fallback = _unnamed_select_fallback(circuit, circuit_id)
                self._attr_name = f"{fallback} {desc_name}"

        # Sync the panel friendly name to the entity registry display name
        # so the UI shows e.g. "Air Conditioner Circuit Priority" while the
        # entity_id stays circuit-based.
        if existing_entity_id and use_circuit_numbers and circuit.name:
            entity_entry = entity_registry.async_get(existing_entity_id)
            if entity_entry:
                expected_name = f"{circuit.name} {desc_name}"
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
                self._attr_name = f"{circuit_identifier} {desc_name}"
            elif name:
                self._attr_name = f"{name} {desc_name}"
            else:
                # v1 behavior: None lets HA handle default naming
                self._attr_name = None

        # Explicitly set entity_id using construct_single_circuit_entity_id
        # which correctly handles 240V two-tab circuits.
        # Only pass unique_id for existing entities (registry lookup);
        # for new entities pass None to get the constructed default.
        constructed_id = construct_single_circuit_entity_id(
            coordinator,
            snapshot,
            "select",
            description.entity_description.key,
            circuit,
            unique_id=self._attr_unique_id if existing_entity_id else None,
        )
        if constructed_id:
            self.entity_id = constructed_id

        self._attr_options = description.options_fn(circuit)
        self._attr_current_option = description.current_option_fn(circuit)

        # Store initial circuit name for change detection in auto-sync
        if not existing_entity_id:
            self._previous_circuit_name: str | None | object = _NAME_UNSET
            _LOGGER.info("Select entity not in registry, will sync on first update")
        else:
            self._previous_circuit_name = circuit.name
            _LOGGER.info(
                "Select entity exists in registry, previous name set to '%s'",
                circuit.name,
            )

    def _get_circuit(self) -> SpanCircuitSnapshot:
        """Get the circuit for this entity."""
        return self.coordinator.data.circuits[self.id]

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        await super().async_will_remove_from_hass()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        _LOGGER.debug("Selecting option: %s", option)
        client = self.coordinator.client
        if not hasattr(client, "set_circuit_priority"):
            _LOGGER.warning("Client does not support priority control")
            return

        priority = CircuitPriority(option)

        try:
            await client.set_circuit_priority(self.id, priority.name)
            await self.coordinator.async_request_refresh()
        except ServiceNotFound as snf:
            _LOGGER.warning(
                "Service not found when setting priority: %s.%s",
                snf.domain,
                snf.service,
            )
            await async_create_span_notification(
                self.hass,
                message="The requested service is not available in the SPAN API.",
                title="Service Not Found",
                notification_id=f"span_panel_service_not_found_{self.id}",
            )
        except SpanPanelServerError:
            warning_msg = (
                f"SPAN API returned a server error attempting "
                f"to change the circuit priority for {self._attr_name}. "
                f"This typically indicates panel firmware doesn't support "
                f"this operation."
            )
            _LOGGER.warning("SPAN API may not support setting priority")
            await async_create_span_notification(
                self.hass,
                message=warning_msg,
                title="SPAN API Error",
                notification_id=f"span_panel_api_error_{self.id}",
            )

    def select_option(self, option: str) -> None:
        """Select an option synchronously."""
        _LOGGER.debug("Selecting option synchronously: %s", option)
        self.hass.create_task(self.async_select_option(option))

    @property
    def available(self) -> bool:
        """Return entity availability.

        Selects become unavailable when panel is offline since they can't change settings.
        """
        if getattr(self.coordinator, "panel_offline", False):
            return False
        return super().available

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return panel position attributes for this circuit."""
        if not self.coordinator.data:
            return None

        circuit = self.coordinator.data.circuits.get(self.id)
        if not circuit:
            return None

        attributes: dict[str, Any] = {}

        tabs_result = construct_tabs_attribute(circuit)
        if tabs_result is not None:
            attributes["tabs"] = tabs_result

        voltage = construct_voltage_attribute(circuit) or 240
        attributes["voltage"] = voltage

        return attributes or None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        snapshot: SpanPanelSnapshot = self.coordinator.data
        circuit = snapshot.circuits.get(self.id)
        if circuit:
            current_circuit_name = circuit.name
            use_circuit_numbers = self.coordinator.config_entry.options.get(
                USE_CIRCUIT_NUMBERS, False
            )
            desc_name = self.description_wrapper.entity_description.name

            if use_circuit_numbers:
                # Circuit-numbers mode: update registry display name, no reload
                if self.entity_id and current_circuit_name:
                    entity_registry = er.async_get(self.hass)
                    entity_entry = entity_registry.async_get(self.entity_id)
                    if entity_entry:
                        # Compute old expected display BEFORE updating
                        # _previous_circuit_name
                        old_display = (
                            f"{self._previous_circuit_name} {desc_name}"
                            if isinstance(self._previous_circuit_name, str)
                            else None
                        )
                        new_display = f"{current_circuit_name} {desc_name}"

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
                        _LOGGER.debug(
                            "User has customized name for %s, skipping sync",
                            self.entity_id,
                        )

                if user_has_override:
                    self._previous_circuit_name = current_circuit_name
                elif self._previous_circuit_name is _NAME_UNSET:
                    _LOGGER.info(
                        "First update: syncing entity name to panel name '%s' for select, requesting reload",
                        current_circuit_name,
                    )
                    self._previous_circuit_name = current_circuit_name
                    self.coordinator.request_reload()
                elif current_circuit_name != self._previous_circuit_name:
                    _LOGGER.info(
                        "Auto-sync detected circuit name change from '%s' to '%s' for select, requesting integration reload",
                        self._previous_circuit_name,
                        current_circuit_name,
                    )
                    self._previous_circuit_name = current_circuit_name
                    self.coordinator.request_reload()

        # Update options and current option based on coordinator data
        circuit = self._get_circuit()
        self._attr_options = self.description_wrapper.options_fn(circuit)
        self._attr_current_option = self.description_wrapper.current_option_fn(circuit)
        super()._handle_coordinator_update()

    def _construct_select_unique_id(
        self,
        coordinator: SpanPanelCoordinator,
        snapshot: SpanPanelSnapshot,
        select_id: str,
    ) -> str:
        """Construct unique ID for select entities."""
        return build_select_unique_id_for_entry(
            coordinator, snapshot, select_id, self._device_name
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SpanPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities for Span Panel."""

    _LOGGER.debug("ASYNC SETUP ENTRY SELECT")

    coordinator = config_entry.runtime_data.coordinator
    snapshot: SpanPanelSnapshot = coordinator.data

    # Get device name from config entry data
    device_name = config_entry.data.get("device_name", config_entry.title)

    entities: list[SpanPanelCircuitsSelect] = []

    for circuit_id, circuit_data in snapshot.circuits.items():
        if not circuit_data.is_user_controllable:
            continue
        # PV/EVSE circuits only get selects if they have a physical breaker
        # (relative_position == "DOWNSTREAM" means connected at a breaker slot)
        if (
            circuit_data.device_type in ("pv", "evse")
            and circuit_data.relative_position != "DOWNSTREAM"
        ):
            continue
        entities.append(
            SpanPanelCircuitsSelect(
                coordinator,
                CIRCUIT_PRIORITY_DESCRIPTION,
                circuit_id,
                circuit_data.name,
                device_name,
            )
        )

    async_add_entities(entities)
