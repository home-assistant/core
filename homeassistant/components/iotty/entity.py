"""Base class for iotty entities."""

import logging

from iottycloud.lightswitch import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import IottyProxy
from .const import DOMAIN
from .coordinator import IottyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class IottyEntity(CoordinatorEntity[IottyDataUpdateCoordinator]):
    """Defines a base iotty entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _iotty_device_name: str
    _iotty_cloud: IottyProxy
    _iotty_device: Device

    def __init__(
        self,
        coordinator: IottyDataUpdateCoordinator,
        iotty_cloud: IottyProxy,
        iotty_device: Device,
    ) -> None:
        """Initialize iotty entity."""
        super().__init__(coordinator)

        _LOGGER.debug(
            "Creating new COVER (%s) %s",
            iotty_device.device_type,
            iotty_device.device_id,
        )

        self._iotty_cloud = iotty_cloud
        self._attr_unique_id = iotty_device.device_id
        self._iotty_device_name = iotty_device.name
        self._iotty_device = iotty_device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, iotty_device.device_id)},
            name=iotty_device.name,
            manufacturer="iotty",
        )
