"""Bosch Smart Home Controller base entity."""

from __future__ import annotations

from boschshcpy import SHCDevice, SHCIntrusionSystem

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


async def async_remove_devices(
    hass: HomeAssistant, entity: SHCBaseEntity, entry_id: str
) -> None:
    """Get item that is removed from session."""
    dev_registry = dr.async_get(hass)
    device = dev_registry.async_get_device(identifiers={(DOMAIN, entity.device_id)})
    if device is not None:
        dev_registry.async_update_device(device.id, remove_config_entry_id=entry_id)


class SHCBaseEntity(Entity):
    """Base representation of a SHC entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, device: SHCDevice | SHCIntrusionSystem, parent_id: str, entry_id: str
    ) -> None:
        """Initialize the generic SHC device."""
        self._device = device
        self._entry_id = entry_id

    async def async_added_to_hass(self) -> None:
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed() -> None:
            if self._device.deleted:
                self.hass.add_job(async_remove_devices(self.hass, self, self._entry_id))
            else:
                self.schedule_update_ha_state()

        self._device.subscribe_callback(self.entity_id, on_state_changed)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        self._device.unsubscribe_callback(self.entity_id)

    @property
    def device_id(self) -> str:
        """Return the device id."""
        return self._device.id


class SHCEntity(SHCBaseEntity):
    """Representation of a SHC device entity."""

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize generic SHC device."""
        self._attr_unique_id = device.serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer=device.manufacturer,
            model=device.device_model,
            name=device.name,
            via_device=(
                DOMAIN,
                device.parent_device_id
                if device.parent_device_id is not None
                else parent_id,
            ),
        )
        super().__init__(device=device, parent_id=parent_id, entry_id=entry_id)

    async def async_added_to_hass(self) -> None:
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed() -> None:
            self.schedule_update_ha_state()

        for service in self._device.device_services:
            service.subscribe_callback(self.entity_id, on_state_changed)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        for service in self._device.device_services:
            service.unsubscribe_callback(self.entity_id)

    @property
    def available(self) -> bool:
        """Return false if status is unavailable."""
        return self._device.status == "AVAILABLE"


class SHCDomainEntity(SHCBaseEntity):
    """Representation of a SHC domain service entity."""

    def __init__(
        self, domain: SHCIntrusionSystem, parent_id: str, entry_id: str
    ) -> None:
        """Initialize the generic SHC device."""
        self._attr_unique_id = domain.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, domain.id)},
            manufacturer=domain.manufacturer,
            model=domain.device_model,
            name=domain.name,
            via_device=(
                DOMAIN,
                parent_id,
            ),
        )
        super().__init__(device=domain, parent_id=parent_id, entry_id=entry_id)

    @property
    def available(self) -> bool:
        """Return false if status is unavailable."""
        return self._device.system_availability
