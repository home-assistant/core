"""Platform for Device tracker integration."""

from fing_agent_api.models import Device

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FingConfigEntry
from .coordinator import FingDataUpdateCoordinator
from .utils import get_icon_from_type


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator = config_entry.runtime_data
    tracked_devices: list[FingTrackedDevice] = []

    entity_registry = er.async_get(hass)

    @callback
    def add_entities() -> None:
        new_entities = [
            FingTrackedDevice(coordinator, device)
            for device in coordinator.data.devices.values()
        ]

        new_ent_unique_ids = {entity.unique_id for entity in new_entities}
        prev_ent_unique_ids = {entity.unique_id for entity in tracked_devices}

        entities_to_remove = [
            entity
            for entity in tracked_devices
            if entity.unique_id not in new_ent_unique_ids
        ]

        entities_to_add = [
            entity
            for entity in new_entities
            if entity.unique_id not in prev_ent_unique_ids
        ]

        # Removes all the entities that are no more tracked by the agent
        for entity in entities_to_remove:
            entity_registry.async_remove(entity.entity_id)
            tracked_devices.remove(entity)

        # Adds all the new entities tracked by the agent
        async_add_entities(entities_to_add)
        tracked_devices.extend(entities_to_add)

    add_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(add_entities))


class FingTrackedDevice(CoordinatorEntity[FingDataUpdateCoordinator], ScannerEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FingDataUpdateCoordinator, device: Device) -> None:
        """Set up FingDevice entity."""
        super().__init__(coordinator)
        self._mac = device.mac
        self._device = coordinator.data.devices[device.mac]

        self._agent_id = coordinator.data.network_id
        if coordinator.data.agent_info is not None:
            self._agent_id = coordinator.data.agent_info.agent_id

        self._attr_name = self._device.name
        self._attr_mac_address = self._mac
        self._attr_unique_id = f"{self._agent_id}-{self.mac_address}"
        self._attr_icon = get_icon_from_type(self._device.type)
        self._attr_entity_registry_enabled_default = True

    @property
    def unique_id(self) -> str | None:
        """Return unique ID of the entity."""
        return f"{self._agent_id}-{self.mac_address}"

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device.ip[0] if self._device.ip else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        attrs: dict[str, str] = {}
        if self._device.type:
            attrs["type"] = self._device.type
        if self._device.make:
            attrs["make"] = self._device.make
        if self._device.model:
            attrs["model"] = self._device.model
        return attrs

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._device.active

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        updated_device_data = self.coordinator.data.devices.get(self._mac)
        if updated_device_data is not None:
            self._device = updated_device_data
            self.async_write_ha_state()
