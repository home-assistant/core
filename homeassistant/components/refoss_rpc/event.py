"""Event entities for Refoss."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import INPUTS_EVENTS_TYPES
from .coordinator import RefossConfigEntry, RefossCoordinator
from .utils import (
    async_remove_refoss_entity,
    get_refoss_entity_name,
    get_refoss_key_instances,
    is_refoss_input_button,
)


@dataclass(frozen=True, kw_only=True)
class RefossEventDescription(EventEntityDescription):
    """Class to describe Refoss event."""

    removal_condition: Callable[[dict, dict, str], bool] | None = None


REFOSS_EVENT: Final = RefossEventDescription(
    key="input",
    translation_key="input",
    device_class=EventDeviceClass.BUTTON,
    event_types=list(INPUTS_EVENTS_TYPES),
    removal_condition=lambda config, status, key: not is_refoss_input_button(
        config, status, key
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RefossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up event for device."""
    entities: list[RefossEvent] = []

    coordinator = config_entry.runtime_data.coordinator
    if TYPE_CHECKING:
        assert coordinator

    key_instances = get_refoss_key_instances(
        coordinator.device.status, REFOSS_EVENT.key
    )

    for key in key_instances:
        if REFOSS_EVENT.removal_condition and REFOSS_EVENT.removal_condition(
            coordinator.device.config, coordinator.device.status, key
        ):
            unique_id = f"{coordinator.mac}-{key}"
            async_remove_refoss_entity(hass, EVENT_DOMAIN, unique_id)
        else:
            entities.append(RefossEvent(coordinator, key, REFOSS_EVENT))

    async_add_entities(entities)


class RefossEvent(CoordinatorEntity[RefossCoordinator], EventEntity):
    """Refoss event entity."""

    entity_description: RefossEventDescription

    def __init__(
        self,
        coordinator: RefossCoordinator,
        key: str,
        description: RefossEventDescription,
    ) -> None:
        """Initialize event entity."""
        super().__init__(coordinator)
        self.input_index = int(key.split(":")[-1])
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)}
        )
        self._attr_unique_id = f"{coordinator.mac}-{key}"
        self._attr_name = get_refoss_entity_name(coordinator.device, key)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_subscribe_input_events(self._async_handle_event)
        )

    @callback
    def _async_handle_event(self, event: dict[str, Any]) -> None:
        """Handle the  button event."""
        if event["id"] == self.input_index:
            self._trigger_event(event["event"])
            self.async_write_ha_state()
