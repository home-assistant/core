"""Implementation of the sensor platform."""

from datetime import timedelta
import logging

from igloohome_api import Api

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
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
    """Do setup the lock entities."""

    try:
        api: Api = entry.runtime_data
        devicesResponse = await api.get_devices()

    except Exception as e:
        raise PlatformNotReady from e
    else:
        async_add_entities(
            new_entities=(
                IgloohomeBatteryEntity(
                    device_id=device.deviceId,
                    device_name=device.deviceName,
                    type=device.type,
                    api=api,
                )
                for device in devicesResponse.payload
                if device.type in ("Lock", "Keypad")
            ),
            update_before_add=True,
        )


class IgloohomeBatteryEntity(IgloohomeBaseEntity, SensorEntity):
    """Implementation of a device that has a battery."""

    _attr_native_unit_of_measurement = "%"
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(self, device_id: str, device_name: str, type: str, api: Api) -> None:
        """Initialize the class."""
        super().__init__(
            device_id=device_id, device_name=device_name, type=type, api=api
        )
        # Set the unique ID of the battery entity.
        self._attr_unique_id = f"battery_{device_id}"

    async def async_update(self) -> None:
        """Update the battery level."""
        try:
            response = await self.api.get_device_info(deviceId=self.device_id)
        except Exception as e:
            raise HomeAssistantError from e
        else:
            self._attr_native_value = response.batteryLevel
