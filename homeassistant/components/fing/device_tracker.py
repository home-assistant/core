"""Platform for Device tracker integration."""

from fing_agent_api.models import Device

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FingConfigEntry
from .coordinator import FingDataUpdateCoordinator
from .utils import get_icon_from_type


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator = config_entry.runtime_data
    tracked_devices: list[FingTrackedDevice] = []

    entity_registry = er.async_get(hass)

    @callback
    def add_entities() -> None:
        new_entities = [
            FingTrackedDevice(coordinator, device)
            for device in coordinator.data.get_devices().values()
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

    def __init__(self, coordinator: FingDataUpdateCoordinator, device: Device) -> None:
        """Set up FingDevice entity."""
        super().__init__(coordinator)
        self._mac = device.mac
        self._device = coordinator.data.get_devices()[device.mac]
        self._network_id = coordinator.data.get_network_id()
        self._attr_has_entity_name = True
        self._attr_name = self._device.name

    @property
    def mac_address(self) -> str:
        """Return mac_address."""
        return self._mac

    @property
    def unique_id(self) -> str | None:
        """Return unique ID of the entity."""
        return f"{self._network_id}-{self.mac_address}"

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return get_icon_from_type(self._device.type)

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
        if self._device.first_seen:
            attrs["first_seen"] = self._device.first_seen
        if self._device.last_changed:
            attrs["last_changed"] = self._device.last_changed
        return attrs

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        return True

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._device.active

    @property
    def source_type(self) -> SourceType:
        """Return source type."""
        return SourceType.ROUTER

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        updated_device_data = self.coordinator.data.get_devices().get(self._mac)
        if updated_device_data is not None:
            self._device = updated_device_data
            self.async_write_ha_state()
