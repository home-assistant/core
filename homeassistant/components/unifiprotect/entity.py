"""Shared Entity definition for UniFi Protect Integration."""
from __future__ import annotations

from typing import Any

from pyunifiprotect.data import ProtectAdoptableDeviceModel

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DEFAULT_ATTRIBUTION, DEFAULT_BRAND, DOMAIN
from .data import ProtectData


class ProtectDeviceEntity(Entity):
    """Base class for UniFi protect entities."""

    _attr_should_poll = False

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel | None = None,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self.data: ProtectData = data

        if device and not hasattr(self, "device"):
            self.device: ProtectAdoptableDeviceModel = device

        if description and not hasattr(self, "entity_description"):
            self.entity_description = description
        elif hasattr(self, "entity_description"):
            description = self.entity_description

        if description is None:
            self._attr_unique_id = f"{self.device.id}"
            self._attr_name = f"{self.device.name}"
        else:
            self._attr_unique_id = f"{self.device.id}_{description.key}"
            name = description.name or ""
            self._attr_name = f"{self.device.name} {name.title()}"

        self._async_set_device_info()
        self._async_update_device_from_protect()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.data.async_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return UniFi Protect device attributes."""
        attrs = super().extra_state_attributes or {}
        return {
            **attrs,
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            **self._extra_state_attributes,
        }

    @callback
    def _async_set_device_info(self) -> None:
        self._attr_device_info = DeviceInfo(
            name=self.device.name,
            manufacturer=DEFAULT_BRAND,
            model=self.device.type,
            via_device=(DOMAIN, self.data.api.bootstrap.nvr.mac),
            sw_version=self.device.firmware_version,
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            configuration_url=self.device.protect_url,
        )

    @callback
    def _async_update_extra_attrs_from_protect(  # pylint: disable=no-self-use
        self,
    ) -> dict[str, Any]:
        """Calculate extra state attributes. Primarily for subclass to override."""
        return {}

    @callback
    def _async_update_device_from_protect(self) -> None:
        """Update Entity object from Protect device."""
        if self.data.last_update_success:
            assert self.device.model
            devices = getattr(self.data.api.bootstrap, f"{self.device.model.value}s")
            self.device = devices[self.device.id]

        self._attr_available = (
            self.data.last_update_success and self.device.is_connected
        )
        self._extra_state_attributes = self._async_update_extra_attrs_from_protect()

    @callback
    def _async_updated_event(self) -> None:
        """Call back for incoming data."""
        self._async_update_device_from_protect()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.async_subscribe_device_id(
                self.device.id, self._async_updated_event
            )
        )
