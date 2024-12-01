"""Implementation of the sensor platform."""

from datetime import timedelta
import logging

from aiohttp import ClientError
from igloohome_api import Api as IgloohomeApi, ApiException, GetDeviceInfoResponse

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IgloohomeConfigEntry
from .entity import IgloohomeBaseEntity

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IgloohomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""

    api = entry.runtime_data[0]
    devices = entry.runtime_data[1]

    async_add_entities(
        (
            IgloohomeBatteryEntity(
                api_device_info=device,
                api=api,
            )
            for device in devices
            if device.batteryLevel is not None
        ),
        update_before_add=True,
    )


class IgloohomeBatteryEntity(IgloohomeBaseEntity, SensorEntity):
    """Implementation of a device that has a battery."""

    _attr_native_unit_of_measurement = "%"
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(
        self, api_device_info: GetDeviceInfoResponse, api: IgloohomeApi
    ) -> None:
        """Initialize the class."""
        super().__init__(api_device_info=api_device_info, api=api)
        # Set the unique ID of the battery entity.
        self._attr_unique_id = f"battery_{api_device_info.deviceId}"

    async def async_update(self) -> None:
        """Update the battery level."""
        try:
            response = await self.api.get_device_info(
                deviceId=self.api_device_info.deviceId
            )
        except (ApiException, ClientError) as e:
            self._attr_available = False
            raise HomeAssistantError from e
        self._attr_available = True
        self._attr_native_value = response.batteryLevel
