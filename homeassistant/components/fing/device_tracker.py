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
    tracked_devices: set[FingTrackedDevice] = set()

    entity_registry = er.async_get(hass)

    @callback
    def add_entities() -> None:
        new_entities = [
            FingTrackedDevice(coordinator, device)
            for device in coordinator.data.devices.values()
        ]

        entities_to_remove = tracked_devices - set(new_entities)
        entities_to_add = set(new_entities) - tracked_devices

        # Removes all the entities that are no more tracked by the agent
        for entity in entities_to_remove:
            entity_registry.async_remove(entity.entity_id)
            tracked_devices.discard(entity)

        # Adds all the new entities tracked by the agent
        async_add_entities(entities_to_add)
        tracked_devices.update(entities_to_add)

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

        agent_id = coordinator.data.network_id
        if coordinator.data.agent_info is not None:
            agent_id = coordinator.data.agent_info.agent_id

        self._attr_mac_address = self._mac
        self._attr_unique_id = f"{agent_id}-{self.mac_address}"
        self._attr_name = self._device.name
        self._attr_icon = get_icon_from_type(self._device.type)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        return True

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._device.active

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

    def check_for_updates(self, new_device: Device) -> bool:
        """Return true if the device has updates."""
        new_device_ip = new_device.ip[0] if new_device.ip else None
        current_device_ip = self._device.ip[0] if self._device.ip else None

        return (
            current_device_ip != new_device_ip
            or self._device.active != new_device.active
            or self._device.type != new_device.type
            or self._device.make != new_device.make
            or self._device.model != new_device.model
            or self._attr_name != new_device.name
            or self._attr_icon != get_icon_from_type(new_device.type)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        updated_device_data = self.coordinator.data.devices.get(self._mac)
        if updated_device_data is not None and self.check_for_updates(
            updated_device_data
        ):
            self._device = updated_device_data
            self._attr_name = updated_device_data.name
            self._attr_icon = get_icon_from_type(updated_device_data.type)
            self.async_write_ha_state()

    def __eq__(self, other):
        """Return true if both entities are equal."""
        return (
            isinstance(other, FingTrackedDevice) and self.unique_id == other.unique_id
        )

    def __hash__(self):
        """Return hash of the entity."""
        return hash(self.unique_id)
