"""Base class for Acmeda Roller Blinds."""

from __future__ import annotations

import aiopulse

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import ACMEDA_ENTITY_REMOVE, DOMAIN, LOGGER


class AcmedaEntity(entity.Entity):
    """Base representation of an Acmeda roller."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, roller: aiopulse.Roller) -> None:
        """Initialize the roller."""
        self.roller = roller

    async def async_remove_and_unregister(self) -> None:
        """Unregister from registries and call entity remove function."""
        LOGGER.error("Removing %s %s", self.__class__.__name__, self.unique_id)

        ent_registry = er.async_get(self.hass)
        if self.entity_id in ent_registry.entities:
            ent_registry.async_remove(self.entity_id)

        dev_registry = dr.async_get(self.hass)
        device = dev_registry.async_get_device(identifiers={(DOMAIN, self.unique_id)})
        if (
            device is not None
            and self.registry_entry is not None
            and self.registry_entry.config_entry_id is not None
        ):
            dev_registry.async_update_device(
                device.id, remove_config_entry_id=self.registry_entry.config_entry_id
            )

        await self.async_remove(force_remove=True)

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        self.roller.callback_subscribe(self.notify_update)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                ACMEDA_ENTITY_REMOVE.format(self.roller.id),
                self.async_remove_and_unregister,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self.roller.callback_unsubscribe(self.notify_update)

    @callback
    def notify_update(self) -> None:
        """Write updated device state information."""
        LOGGER.debug("Device update notification received: %s", self.name)
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this roller."""
        return str(self.roller.id)

    @property
    def device_id(self) -> str:
        """Return the ID of this roller."""
        return self.roller.id  # type: ignore[no-any-return]

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return the device info."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Rollease Acmeda",
            name=self.roller.name,
            via_device=(DOMAIN, self.roller.hub.id),
        )
