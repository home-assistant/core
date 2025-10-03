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
    entity_registry = er.async_get(hass)
    tracked_devices: set[str] = set()

    @callback
    def add_entities() -> None:
        latest_devices = set(coordinator.data.devices.keys())

        devices_to_remove = tracked_devices - set(latest_devices)
        devices_to_add = set(latest_devices) - tracked_devices

        entities_to_remove = []
        for entity_entry in entity_registry.entities.values():
            if entity_entry.config_entry_id != config_entry.entry_id:
                continue
            try:
                _, mac = entity_entry.unique_id.rsplit("-", 1)
                if mac in devices_to_remove:
                    entities_to_remove.append(entity_entry.entity_id)
            except ValueError:
                continue

        for entity_id in entities_to_remove:
            entity_registry.async_remove(entity_id)

        entities_to_add = []
        for mac_addr in devices_to_add:
            device = coordinator.data.devices[mac_addr]
            entities_to_add.append(FingTrackedDevice(coordinator, device))

        tracked_devices.clear()
        tracked_devices.update(latest_devices)
        async_add_entities(entities_to_add)

    add_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(add_entities))


class FingTrackedDevice(CoordinatorEntity[FingDataUpdateCoordinator], ScannerEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FingDataUpdateCoordinator, device: Device) -> None:
        """Set up FingDevice entity."""
        super().__init__(coordinator)

        self._device = device
        agent_id = coordinator.data.network_id
        if coordinator.data.agent_info is not None:
            agent_id = coordinator.data.agent_info.agent_id

        self._attr_mac_address = self._device.mac
        self._attr_unique_id = f"{agent_id}-{self._attr_mac_address}"
        self._attr_name = self._device.name
        self._attr_icon = get_icon_from_type(self._device.type)

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._device.active

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device.ip[0] if self._device.ip else None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable entity by default."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        attrs: dict[str, str] = {}
        if self._device.type:
            attrs["type"] = self._device.type
        if self._device.make:
            attrs["manufacturer"] = self._device.make
        if self._device.model:
            attrs["model"] = self._device.model
        return attrs

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self._attr_unique_id

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
        updated_device_data = self.coordinator.data.devices.get(self._device.mac)
        if updated_device_data is not None and self.check_for_updates(
            updated_device_data
        ):
            self._device = updated_device_data
            self._attr_name = updated_device_data.name
            self._attr_icon = get_icon_from_type(updated_device_data.type)
            self.async_write_ha_state()
