"""The MusicCast integration."""

from __future__ import annotations

from aiomusiccast.capabilities import Capability

from homeassistant.const import ATTR_CONNECTIONS, ATTR_VIA_DEVICE
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND, DEFAULT_ZONE, DOMAIN, ENTITY_CATEGORY_MAPPING
from .coordinator import MusicCastDataUpdateCoordinator


class MusicCastEntity(CoordinatorEntity[MusicCastDataUpdateCoordinator]):
    """Defines a base MusicCast entity."""

    def __init__(
        self,
        *,
        name: str,
        icon: str,
        coordinator: MusicCastDataUpdateCoordinator,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the MusicCast entity."""
        super().__init__(coordinator)
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_icon = icon
        self._attr_name = name


class MusicCastDeviceEntity(MusicCastEntity):
    """Defines a MusicCast device entity."""

    _zone_id: str = DEFAULT_ZONE

    @property
    def device_id(self):
        """Return the ID of the current device."""
        if self._zone_id == DEFAULT_ZONE:
            return self.coordinator.data.device_id
        return f"{self.coordinator.data.device_id}_{self._zone_id}"

    @property
    def device_name(self):
        """Return the name of the current device."""
        return self.coordinator.data.zones[self._zone_id].name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this MusicCast device."""

        device_info = DeviceInfo(
            name=self.device_name,
            identifiers={
                (
                    DOMAIN,
                    self.device_id,
                )
            },
            manufacturer=BRAND,
            model=self.coordinator.data.model_name,
            sw_version=self.coordinator.data.system_version,
        )

        if self._zone_id == DEFAULT_ZONE:
            device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, format_mac(mac))
                for mac in self.coordinator.data.mac_addresses.values()
            }
        else:
            device_info[ATTR_VIA_DEVICE] = (DOMAIN, self.coordinator.data.device_id)

        return device_info

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        # All entities should register callbacks to update HA when their state changes
        self.coordinator.musiccast.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        await super().async_will_remove_from_hass()
        self.coordinator.musiccast.remove_callback(self.async_write_ha_state)


class MusicCastCapabilityEntity(MusicCastDeviceEntity):
    """Base Entity type for all capabilities."""

    def __init__(
        self,
        coordinator: MusicCastDataUpdateCoordinator,
        capability: Capability,
        zone_id: str | None = None,
    ) -> None:
        """Initialize a capability based entity."""
        if zone_id is not None:
            self._zone_id = zone_id
        self.capability = capability
        super().__init__(name=capability.name, icon="", coordinator=coordinator)
        self._attr_entity_category = ENTITY_CATEGORY_MAPPING.get(capability.entity_type)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.device_id}_{self.capability.id}"
