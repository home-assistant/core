"""Support for Acmeda Roller Blind Batteries."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AcmedaConfigEntry
from .const import ACMEDA_HUB_UPDATE
from .entity import AcmedaEntity
from .helpers import async_add_acmeda_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AcmedaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Acmeda Rollers from a config entry."""
    hub = config_entry.runtime_data

    current: set[int] = set()

    @callback
    def async_add_acmeda_sensors() -> None:
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


class AcmedaBattery(AcmedaEntity, SensorEntity):
    """Representation of an Acmeda cover sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the device."""
        return self.roller.battery  # type: ignore[no-any-return]
