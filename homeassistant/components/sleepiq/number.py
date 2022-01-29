"""Support for SleepIQ Number."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sleep numbers."""
    data = hass.data[DOMAIN][config_entry.entry_id][SLEEPIQ_DATA]
    status_coordinator = hass.data[DOMAIN][config_entry.entry_id][
        SLEEPIQ_STATUS_COORDINATOR
    ]

    entities: list[SleepNumberEntity] = []
    for bed in data.beds.values():
        for sleeper in bed.sleepers:
            entities.append(SleepNumberEntity(sleeper, bed, status_coordinator))

    async_add_entities(entities)


class SleepNumberEntity(CoordinatorEntity, NumberEntity):
    """Representation of a sleep number."""

    _attr_icon = "mdi:gauge"
    _attr_max_value = 100
    _attr_min_value = 0
    _attr_step = 5
    _attr_mode = NumberMode.BOX

    def __init__(self, sleeper, bed, status_coordinator):
        super().__init__(status_coordinator)
        self._bed = bed
        self._sleeper = sleeper
        self._name = f"{bed.name} {sleeper.name} Sleep Number"
        self._unique_id = f"{bed.id}-{sleeper.side}-SN"

    @property
    def value(self) -> int:
        """Return the current sleep number value."""
        return self._sleeper.sleep_number

    async def async_set_value(self, value: float) -> None:
        """Set the sleep number value."""
        if not value.is_integer():
            raise ValueError(
                f"Can't set the sleep number value to {value}, must be an integer."
            )
        await self._sleeper.set_sleepnumber(int(value))

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._bed.id)},
            connections={(device_registry.CONNECTION_NETWORK_MAC, self._bed.mac_addr)},
            manufacturer="SleepNumber",
            name=self._bed.name,
            model=self._bed.model,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the binary sensor."""
        return self._unique_id
