"""Representation of an EnOcean device."""

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(
        self,
        enocean_entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        device_class: SensorDeviceClass
        | BinarySensorDeviceClass
        | SwitchDeviceClass
        | CoverDeviceClass
        | None = None,
        entity_category: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__()

        # set base class attributes
        if enocean_entity_id.unique_id:
            self._attr_translation_key = enocean_entity_id.unique_id
        else:
            self._attr_name = None

        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._attr_device_class = device_class
        self._attr_entity_category = (
            EntityCategory(entity_category) if entity_category else None
        )

        # define EnOcean-specific attributes
        self.__enocean_entity_id: EnOceanEntityID = enocean_entity_id
        self.__gateway: EnOceanHomeAssistantGateway = gateway

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        uid: str = self.__enocean_entity_id.to_string()
        return uid

    @property
    def enocean_entity_id(self) -> EnOceanEntityID:
        """Return the Entity ID of the entity."""
        return self.__enocean_entity_id

    @property
    def gateway(self) -> EnOceanHomeAssistantGateway:
        """Return the gateway instance."""
        return self.__gateway

    @property
    def device_info(self) -> DeviceInfo | None:
        """Get device info."""
        device_properties = self.gateway.get_device_properties(
            self.enocean_entity_id.device_address
        )

        if self.gateway.chip_id == self.enocean_entity_id.device_address:
            return DeviceInfo(
                {
                    "identifiers": {
                        (DOMAIN, self.enocean_entity_id.device_address.to_string())
                    },
                    "name": device_properties.device_name,
                    "manufacturer": device_properties.device_type.manufacturer,
                    "model": device_properties.device_type.model,
                    "serial_number": self.enocean_entity_id.device_address.to_string(),
                    "sw_version": self.gateway.sw_version,
                    "hw_version": self.gateway.chip_version,
                }
            )

        return DeviceInfo(
            {
                "identifiers": {
                    (DOMAIN, self.enocean_entity_id.device_address.to_string())
                },
                "name": device_properties.device_name,
                "manufacturer": device_properties.device_type.manufacturer,
                "model": device_properties.device_type.model,
                "serial_number": self.enocean_entity_id.device_address.to_string(),
                "sw_version": None,
                "hw_version": None,
                "model_id": "EEP " + device_properties.device_type.eep.to_string(),
                "via_device": (DOMAIN, self.gateway.chip_id.to_string()),
            }
        )
