"""Parent class for every OSO Energy device."""

from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.const import (
    OSOEnergyBinarySensorData,
    OSOEnergySensorData,
    OSOEnergyWaterHeaterData,
)

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

MANUFACTURER = "OSO Energy"


class OSOEnergyEntity[
    _OSOEnergyT: (
        OSOEnergyBinarySensorData,
        OSOEnergySensorData,
        OSOEnergyWaterHeaterData,
    )
](Entity):
    """Initiate OSO Energy Base Class."""

    _attr_has_entity_name = True

    def __init__(self, osoenergy: OSOEnergy, entity_data: _OSOEnergyT) -> None:
        """Initialize the instance."""
        self.osoenergy = osoenergy
        self.entity_data = entity_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entity_data.device_id)},
            manufacturer=MANUFACTURER,
            model=entity_data.device_type,
            name=entity_data.device_name,
        )
