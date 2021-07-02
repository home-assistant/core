"""Base class for Acmeda Roller Blinds."""
import aiopulse

from homeassistant.core import callback
from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import async_get_registry as get_dev_reg
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_get_registry as get_ent_reg

from .const import ACMEDA_ENTITY_REMOVE, DOMAIN, LOGGER


class AcmedaBase(entity.Entity):
    """Base representation of an Acmeda roller."""

    _attr_should_poll = False

    def __init__(self, roller: aiopulse.Roller) -> None:
        """Initialize the roller."""
        self.roller = roller
        self.device_id = self.roller.id
        self._attr_unique_id = self.roller.id
        self._attr_name = self.roller.name

    async def async_remove_and_unregister(self):
        """Unregister from entity and device registry and call entity remove function."""
        LOGGER.error("Removing %s %s", self.__class__.__name__, self.unique_id)

        ent_registry = await get_ent_reg(self.hass)
        if self.entity_id in ent_registry.entities:
            ent_registry.async_remove(self.entity_id)

        dev_registry = await get_dev_reg(self.hass)
        device = dev_registry.async_get_device(identifiers={(DOMAIN, self.unique_id)})
        if device is not None:
            dev_registry.async_update_device(
                device.id, remove_config_entry_id=self.registry_entry.config_entry_id
            )

        await self.async_remove(force_remove=True)

    async def async_added_to_hass(self):
        """Entity has been added to hass."""
        self.roller.callback_subscribe(self.notify_update)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                ACMEDA_ENTITY_REMOVE.format(self.roller.id),
                self.async_remove_and_unregister,
            )
        )

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self.roller.callback_unsubscribe(self.notify_update)

    @callback
    def notify_update(self):
        """Write updated device state information."""
        LOGGER.debug("Device update notification received: %s", self.name)
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.roller.name,
            "manufacturer": "Rollease Acmeda",
            "via_device": (DOMAIN, self.roller.hub.id),
        }
