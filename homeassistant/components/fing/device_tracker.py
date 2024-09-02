"""Platform for Device tracker integration."""

# See cover.py for more details.
# Note how both entities for each roller sensor (battry and illuminance) are added at
# the same time to the same list. This way only a single async_add_devices call is
# required.
from collections.abc import Sequence

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FingConfigEntry
from .coordinator import FingDataUpdateCoordinator
from .fing_api.models import Device
from .utils import get_icon_from_type


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""

    coordinator = config_entry.runtime_data
    new_entities = [
        FingTrackedDevice(coordinator, device)
        for device in coordinator.data.get_devices().values()
    ]

    await remove_old_entities(hass, config_entry, new_entities)
    async_add_entities(new_entities)


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
        self._device = self.coordinator.data.get_devices()[self._mac]
        self.async_write_ha_state()


async def remove_old_entities(
    hass: HomeAssistant,
    config_entry: FingConfigEntry,
    new_entities: Sequence[FingTrackedDevice],
):
    """Remove all the old entities."""

    device_reg = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    instantiated_entities = entity_registry.entities.get_entries_for_config_entry_id(
        config_entry.entry_id
    )

    new_entities_ids = {entity.unique_id for entity in new_entities}
    entities_to_remove = [
        entity
        for entity in instantiated_entities
        if entity.unique_id not in new_entities_ids
    ]

    for entity in entities_to_remove:
        entity_registry.async_remove(entity.entity_id)
        if entity.device_id is not None:
            device_reg.async_update_device(
                entity.device_id, remove_config_entry_id=config_entry.entry_id
            )
