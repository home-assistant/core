"""Sensor platform for EnergyID directives."""

from typing import Any, override

from energyid_webhooks.directives import DirectiveResource

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    EnergyIDConfigEntry,
    EnergyIDDirectiveCoordinator,
    EnergyIDDirectiveSnapshot,
    async_directives_enabled,
)

PARALLEL_UPDATES = 0

SIGNAL_TO_STATE = {
    "--": "very_bad_moment",
    "-": "bad_moment",
    "0": "neutral",
    "+": "good_moment",
    "++": "very_good_moment",
}
DIRECTIVE_STATES = list(SIGNAL_TO_STATE.values())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyIDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up directive sensors and discover newly granted directives."""
    coordinator = entry.runtime_data.directive_coordinator
    directives_enabled = async_directives_enabled(entry)
    entity_registry = er.async_get(hass)
    known_directives: set[str] = set()
    unique_id_prefix = f"{entry.entry_id}_"

    @callback
    def _async_sync_directives() -> None:
        """Add newly granted directives and prune revoked ones."""
        # The granted set is only trusted after a successful fetch.
        if not coordinator.last_update_success:
            return
        resources = coordinator.data.resources if directives_enabled else {}
        authorized_unique_ids = {
            f"{unique_id_prefix}{directive_id}" for directive_id in resources
        }
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if (
                registry_entry.platform == DOMAIN
                and registry_entry.unique_id not in authorized_unique_ids
            ):
                entity_registry.async_remove(registry_entry.entity_id)
                known_directives.discard(
                    registry_entry.unique_id.removeprefix(unique_id_prefix)
                )

        new_directives = set(resources) - known_directives
        if not new_directives:
            return
        known_directives.update(new_directives)
        async_add_entities(
            EnergyIDDirectiveSensor(entry, coordinator, resources[directive_id])
            for directive_id in new_directives
        )

    _async_sync_directives()
    if directives_enabled:
        entry.async_on_unload(coordinator.async_add_listener(_async_sync_directives))


class EnergyIDDirectiveSensor(
    CoordinatorEntity[EnergyIDDirectiveCoordinator], SensorEntity
):
    """Represent the current state of an EnergyID directive."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_options = DIRECTIVE_STATES
    _attr_translation_key = "directive"

    def __init__(
        self,
        entry: EnergyIDConfigEntry,
        coordinator: EnergyIDDirectiveCoordinator,
        resource: DirectiveResource,
    ) -> None:
        """Initialize a directive sensor."""
        super().__init__(coordinator)
        self.directive_id = resource.id
        self._attr_unique_id = f"{entry.entry_id}_{resource.id}"
        self._attr_translation_placeholders = {"directive_name": resource.title}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.client.recordName or coordinator.client.device_name,
            manufacturer="EnergyID",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def snapshot(self) -> EnergyIDDirectiveSnapshot:
        """Return the fetched schedule of this directive."""
        return self.coordinator.data.schedules[self.directive_id]

    @property
    @override
    def available(self) -> bool:
        """Return whether the schedule of this directive was fetched."""
        return (
            super().available and self.directive_id in self.coordinator.data.schedules
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return the state key of the current signal."""
        current = self.snapshot.current
        return SIGNAL_TO_STATE.get(current.signal) if current else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the next scheduled change for automations."""
        next_change = self.snapshot.next_change
        return {
            "next_change": next_change.timestamp.isoformat() if next_change else None,
            "next_state": SIGNAL_TO_STATE.get(next_change.signal)
            if next_change
            else None,
        }
