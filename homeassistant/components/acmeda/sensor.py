"""Support for Acmeda Roller Blind Batteries."""
import asyncio

from homeassistant.const import DEVICE_CLASS_BATTERY, UNIT_PERCENTAGE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.icon import icon_for_battery_level

from .base import AcmedaBase
from .const import ACMEDA_HUB_UPDATE
from .helpers import add_entities


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Acmeda Rollers from a config entry."""
    update_lock = asyncio.Lock()
    current = set()

    async def async_update():
        async with update_lock:
            await add_entities(
                hass, AcmedaBattery, config_entry, current, async_add_entities
            )

    async_dispatcher_connect(
        hass, ACMEDA_HUB_UPDATE.format(config_entry.entry_id), async_update
    )


class AcmedaBattery(AcmedaBase):
    """Representation of a Acmeda cover device."""

    device_class = DEVICE_CLASS_BATTERY
    unit_of_measurement = UNIT_PERCENTAGE

    @property
    def name(self):
        """Return the name of roller."""
        return f"{super().name} Battery"

    @property
    def state(self):
        """Return the state of the device."""
        return self.roller.battery

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return icon_for_battery_level(battery_level=self.roller.battery)
