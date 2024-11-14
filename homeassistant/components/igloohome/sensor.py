"""Implementation of the sensor platform."""

import logging

from aiohttp import ClientError
from igloohome_api import Api

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyConfigEntry
from .entity import BaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: MyConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Do setup the lock entities."""

    try:
        api: Api = entry.runtime_data
        devicesResponse = await api.get_devices()

        entities = [
            BatteryBasedDevice(
                device_id=device.deviceId,
                device_name=device.deviceName,
                type=device.type,
                api=api,
            )
            for device in devicesResponse.payload
            if device.type in ("Lock", "Keypad")
        ]

        async_add_entities(entities, update_before_add=True)
    except ClientError as e:
        raise PlatformNotReady from e


class BatteryBasedDevice(BaseEntity, SensorEntity):
    """Implementation of a device that has a battery."""

    _attr_native_unit_of_measurement = "%"

    def __init__(self, device_id: str, device_name: str, type: str, api: Api) -> None:
        """Initialize the class."""
        super().__init__(
            device_id=device_id, device_name=device_name, type=type, api=api
        )
        self._attr_device_class = SensorDeviceClass.BATTERY
        # Set the unique ID of the battery entity.
        self._attr_unique_id = f"battery_{device_id}"

    async def async_update(self) -> None:
        """Update the battery level."""
        try:
            response = await self.api.get_device_info(deviceId=self.device_id)
            self._attr_native_value = response.batteryLevel
        except ClientError as e:
            _LOGGER.log(
                logging.ERROR,
                "Failed to update battery level for deviceId %s. cause=%s",
                self.device_id,
                e.__str__,
            )
