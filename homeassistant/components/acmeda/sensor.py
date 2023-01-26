"""Support for Acmeda Roller Blind Batteries."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import AcmedaBase
from .const import ACMEDA_HUB_UPDATE, DOMAIN
from .helpers import async_add_acmeda_entities
from .hub import PulseHub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Acmeda Rollers from a config entry."""
    hub: PulseHub = hass.data[DOMAIN][config_entry.entry_id]

    current: set[int] = set()

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

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def name(self) -> str:
        """Return the name of roller."""
        return f"{super().name} Battery"

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the device."""
        return self.roller.battery
