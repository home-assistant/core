"""Representation of an EnOcean device."""

from dataclasses import dataclass

from enocean_async import EURID, Gateway
from enocean_async.semantics.entity import EntityCategory as LibEntityCategory

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

LIB_ENTITY_CATEGORY_MAP: dict[str, EntityCategory | None] = {
    LibEntityCategory.CONFIG: EntityCategory.CONFIG,
    LibEntityCategory.DIAGNOSTIC: EntityCategory.DIAGNOSTIC,
    LibEntityCategory.DEFAULT: None,
}


@dataclass
class EnOceanEntityID:
    """Uniquely identifies an EnOcean entity by its device EURID and a per-entity string."""

    device_address: EURID
    unique_id: str | None = None

    def __str__(self) -> str:
        """Return string representation used as the HA unique_id."""
        if self.unique_id:
            return f"{self.device_address!s}.{self.unique_id}"
        return str(self.device_address)


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(
        self,
        enocean_entity_id: EnOceanEntityID,
        gateway: Gateway,
    ) -> None:
        """Initialize the entity."""
        super().__init__()

        self._attr_has_entity_name = True
        self._attr_should_poll = False

        if enocean_entity_id.unique_id:
            self._attr_translation_key = enocean_entity_id.unique_id
        else:
            self._attr_name = None

        self.__enocean_entity_id: EnOceanEntityID = enocean_entity_id
        self.__gateway: Gateway = gateway

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return str(self.__enocean_entity_id)

    @property
    def enocean_entity_id(self) -> EnOceanEntityID:
        """Return the Entity ID of the entity."""
        return self.__enocean_entity_id

    @property
    def gateway(self) -> Gateway:
        """Return the gateway instance."""
        return self.__gateway

    @property
    def device_info(self) -> DeviceInfo | None:
        """Get device info."""
        address = self.__enocean_entity_id.device_address
        gateway_eurid = self.__gateway.eurid
        if address == gateway_eurid:
            return DeviceInfo(identifiers={(DOMAIN, str(gateway_eurid))})
        spec = self.__gateway.device_spec(address)

        dt = spec.device_type
        manufacturer = str(dt.manufacturer) if dt.manufacturer is not None else None

        return DeviceInfo(
            identifiers={(DOMAIN, str(address))},
            manufacturer=manufacturer,
            model=dt.model,
            model_id=f"EEP {dt.eep}",
            serial_number=str(address),
            via_device=(DOMAIN, str(gateway_eurid)),
        )
