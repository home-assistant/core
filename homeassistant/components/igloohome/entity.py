"""Implementation of a base entity that belongs to all igloohome devices."""

from igloohome_api import Api

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class IgloohomeBaseEntity(Entity):
    """A base entity that is a part of all igloohome devices."""

    _attr_has_entity_name = True

    def __init__(self, device_id: str, device_name: str, type: str, api: Api) -> None:
        """Initialize the base device class."""
        self.device_id = device_id
        self.device_name = device_name
        self.type = type
        self.api = api

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return the device info."""
        return dr.DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.device_id)
            },
            name=self.device_name,
            model=self.type,
        )
