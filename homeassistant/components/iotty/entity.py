"""Base class for iotty entities."""

import logging
from typing import cast

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

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, cast(str, self._attr_unique_id))},
            name=self._iotty_device_name,
            manufacturer="iotty",
        )
