"""Support for OSO Energy binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.const import OSOEnergyBinarySensorData

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import OSOEnergyEntity


@dataclass(frozen=True, kw_only=True)
class OSOEnergyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing OSO Energy heater binary sensor entities."""

    value_fn: Callable[[OSOEnergy], bool]


SENSOR_TYPES: dict[str, OSOEnergyBinarySensorEntityDescription] = {
    "power_save": OSOEnergyBinarySensorEntityDescription(
        key="power_save",
        translation_key="power_save",
        value_fn=lambda entity_data: entity_data.state,
    ),
    "extra_energy": OSOEnergyBinarySensorEntityDescription(
        key="extra_energy",
        translation_key="extra_energy",
        value_fn=lambda entity_data: entity_data.state,
    ),
    "heater_state": OSOEnergyBinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        value_fn=lambda entity_data: entity_data.state,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OSO Energy binary sensor."""
    osoenergy: OSOEnergy = hass.data[DOMAIN][entry.entry_id]
    entities = [
        OSOEnergyBinarySensor(osoenergy, sensor_type, dev)
        for dev in osoenergy.session.device_list.get("binary_sensor", [])
        if (sensor_type := SENSOR_TYPES.get(dev.osoEnergyType.lower()))
    ]

    async_add_entities(entities, True)


class OSOEnergyBinarySensor(
    OSOEnergyEntity[OSOEnergyBinarySensorData], BinarySensorEntity
):
    """OSO Energy Sensor Entity."""

    entity_description: OSOEnergyBinarySensorEntityDescription

    def __init__(
        self,
        instance: OSOEnergy,
        description: OSOEnergyBinarySensorEntityDescription,
        entity_data: OSOEnergyBinarySensorData,
    ) -> None:
        """Set up OSO Energy binary sensor."""
        super().__init__(instance, entity_data)

        device_id = entity_data.device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.entity_data)

    async def async_update(self) -> None:
        """Update all data for OSO Energy."""
        await self.osoenergy.session.update_data()
        self.entity_data = await self.osoenergy.binary_sensor.get_sensor(
            self.entity_data
        )
