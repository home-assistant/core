"""Representation of an EnOcean device."""

from enocean_async import EURID, Gateway

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class EnOceanEntityID:
    """An EnOcean entity is uniquely identified by its device's EnOcean Unique Radio Identifier (EURID) and a unique ID string for the entity."""

    def __init__(self, device_address: EURID, unique_id: str | None = None) -> None:
        """Construct an EnOcean entity ID."""
        self.__device_address = device_address
        self.__unique_id: str | None = unique_id

    @property
    def device_address(self) -> EURID:
        """Return the device address part of the entity ID."""
        return self.__device_address

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID part of the entity ID."""
        return self.__unique_id

    def __str__(self) -> str:
        """Return a string representation of the entity."""
        if self.__unique_id:
            return f"{self.__device_address!s}.{self.__unique_id}"
        return f"{self.__device_address!s}"

    def __hash__(self) -> int:
        """Return the hash of the entity ID."""
        return hash((int(self.__device_address), self.unique_id))

    def __eq__(self, other: object) -> bool:
        """Check equality with another entity ID."""
        if not isinstance(other, EnOceanEntityID):
            return NotImplemented
        return (int(self.__device_address), self.unique_id) == (
            int(other.device_address),
            other.unique_id,
        )


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(
        self,
        enocean_entity_id: EnOceanEntityID,
        gateway: Gateway,
        gateway_eurid: EURID,
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
        self.__gateway_eurid: EURID = gateway_eurid

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
        spec = self.__gateway.device_spec(address)
        if spec is None:
            return None

        dt = spec.device_type
        manufacturer = str(dt.manufacturer) if dt.manufacturer is not None else None

        return DeviceInfo(
            identifiers={(DOMAIN, str(address))},
            manufacturer=manufacturer,
            model=dt.model,
            model_id=f"EEP {dt.eep}",
            serial_number=str(address),
            via_device=(DOMAIN, str(self.__gateway_eurid)),
        )
