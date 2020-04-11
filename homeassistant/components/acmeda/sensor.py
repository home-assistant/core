"""Support for Acmeda Roller Blind Batteries."""
import asyncio

import aiopulse

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    DEVICE_CLASS_BATTERY,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers import entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.icon import icon_for_battery_level

from .base import AcmedaBase
from .const import ACMEDA_HUB_UPDATE, DOMAIN, LOGGER
from .helpers import remove_devices


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Acmeda Rollers from a config entry."""
    hub = hass.data[DOMAIN][config_entry.data["host"]]

    update_lock = asyncio.Lock()
    current = {}

    async def async_update():
        """Add any new sensors."""
        async with update_lock:
            LOGGER.debug("Looking for new sensors on: %s", hub.host)

            api = hub.api.rollers

            new_items = []

            for unique_id, roller in api.items():
                if unique_id not in current:
                    LOGGER.debug("New sensor %s", unique_id)
                    new_item = AcmedaBattery(hass, roller)
                    current[unique_id] = new_item
                    new_items.append(new_item)

            async_add_entities(new_items)

            removed_items = []
            for unique_id, element in current.items():
                if unique_id not in api:
                    LOGGER.debug("Removing sensor %s", unique_id)
                    removed_items.append(element)

            for element in removed_items:
                del current[element.unique_id]

            await remove_devices(hass, config_entry, removed_items)

    async_dispatcher_connect(hass, ACMEDA_HUB_UPDATE, async_update)


class AcmedaBattery(AcmedaBase, entity.Entity):
    """Representation of a Acmeda cover device."""

    device_class = DEVICE_CLASS_BATTERY
    unit_of_measurement = UNIT_PERCENTAGE

    def __init__(self, hass, roller: aiopulse.Roller):
        """Initialize the roller."""
        super().__init__(hass, roller)

    @property
    def name(self):
        """Return the name of roller."""
        return super().name + " Battery"

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self.roller.battery

    @property
    def state(self):
        """Return the state of the device."""
        return self.roller.battery

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)

        attr[ATTR_BATTERY_LEVEL] = self.roller.battery

        return attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return icon_for_battery_level(battery_level=self.roller.battery)
