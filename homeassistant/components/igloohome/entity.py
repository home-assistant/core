"""Implementation of a base entity that belongs to all igloohome devices."""

from igloohome_api import Api as IgloohomeApi, GetDeviceInfoResponse

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class IgloohomeBaseEntity(Entity):
    """A base entity that is a part of all igloohome devices."""

    _attr_has_entity_name = True

    def __init__(
        self, api_device_info: GetDeviceInfoResponse, api: IgloohomeApi, unique_key: str
    ) -> None:
        """Initialize the base device class."""
        self.api = api
        self.api_device_info = api_device_info
        # Register the entity as part of a device.
        self._attr_device_info = dr.DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, api_device_info.deviceId)
            },
            name=api_device_info.deviceName,
            model=api_device_info.type,
        )
        # Set the unique ID of the entity.
        self._attr_unique_id = f"{unique_key}_{api_device_info.deviceId}"
