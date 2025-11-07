"""Representation of an EnOcean device."""

from homeassistant_enocean.address import EnOceanDeviceAddress
from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.config_entries import _LOGGER
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(
        self,
        enocean_entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
    ) -> None:
        """Initialize the entity."""
        super().__init__()

        # set base class attributes
        self._attr_translation_key = enocean_entity_id.name
        self._attr_has_entity_name = True
        self._attr_should_poll = False

        # define EnOcean-specific attributes
        self.__enocean_entity_id: EnOceanEntityID = enocean_entity_id
        self.__gateway: EnOceanHomeAssistantGateway = gateway

        gateway.register_entity_callback(self.__enocean_entity_id, self.__update)

    async def async_added_to_hass(self) -> None:
        """Get gateway ID and register callback."""
        _LOGGER.warning(
            "Unique_id: %s, device_id: %s, entity_name: %s, Friendly_name: %s",
            self.unique_id,
            self.gateway.get_device_properties(self.enocean_id).device_name,
            self.name,
            self._friendly_name_internal(),
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        uid: str = self.__enocean_entity_id.to_string()
        return uid
        # return f"{self.__enocean_entity_id.device_address.to_string()}.{self.platform.domain}.{self.__enocean_entity_id.name}"

    @property
    def enocean_entity_id(self) -> EnOceanEntityID:
        """Return the Entity ID of the entity."""
        return self.__enocean_entity_id

    @property
    def enocean_id(self) -> EnOceanDeviceAddress:
        """Return the EnOcean device id."""
        return self.__enocean_entity_id.device_address

    @property
    def gateway(self) -> EnOceanHomeAssistantGateway:
        """Return the gateway instance."""
        return self.__gateway

    @property
    def gateway_id(self) -> EnOceanDeviceAddress:
        """Return the gateway's chip id."""
        return self.__gateway.chip_id

    @property
    def device_info(self) -> DeviceInfo | None:
        """Get device info."""
        device_properties = self.gateway.get_device_properties(self.enocean_id)

        return DeviceInfo(
            {
                "identifiers": {
                    (DOMAIN, self.__enocean_entity_id.device_address.to_string())
                },
                "name": device_properties.device_name,
                "manufacturer": device_properties.device_type.manufacturer,
                "model": device_properties.device_type.model,
                "serial_number": self.__enocean_entity_id.device_address.to_string(),
                "sw_version": None,
                "hw_version": None,
                "model_id": "EEP " + device_properties.device_type.eep.to_string(),
                "via_device": (DOMAIN, self.gateway_id.to_string()),
            }
        )

    def __update(self) -> None:
        """Notify entity of changes."""
        self.schedule_update_ha_state()
