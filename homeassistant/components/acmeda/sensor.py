"""Support for Acmeda Roller Blind Batteries."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .base import AcmedaBase
from .const import ACMEDA_HUB_UPDATE, DOMAIN
from .helpers import async_add_acmeda_entities


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Acmeda Rollers from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    current = set()

    @callback
    def async_add_acmeda_sensors():
        async_add_acmeda_entities(
            hass, AcmedaBattery, config_entry, current, async_add_entities
        )

    hub.cleanup_callbacks.append(
        async_dispatcher_connect(
            hass,
            ACMEDA_HUB_UPDATE.format(config_entry.entry_id),
            async_add_acmeda_sensors,
        )
    )


class AcmedaBattery(AcmedaBase, SensorEntity):
    """Representation of a Acmeda cover device."""

    device_class = DEVICE_CLASS_BATTERY
    unit_of_measurement = PERCENTAGE

    @property
    def name(self):
        """Return the name of roller."""
        return f"{super().name} Battery"

    @property
    def state(self):
        """Return the state of the device."""
        return self.roller.battery
