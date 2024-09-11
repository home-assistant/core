"""Base class for iotty entities."""

import logging

from iottycloud.lightswitch import Device

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import IottyProxy
from .coordinator import IottyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class IottyEntity(CoordinatorEntity[IottyDataUpdateCoordinator]):
    """Defines a base iotty entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_entity_category = None
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
