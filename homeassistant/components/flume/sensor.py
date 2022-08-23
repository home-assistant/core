"""Sensor for displaying the number of result from Flume."""
from datetime import timedelta
from numbers import Number

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_QUERIES_SENSOR,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_TIMEZONE,
    KEY_DEVICE_TYPE,
)
from .coordinator import FlumeDeviceDataUpdateCoordinator
from .entity import FlumeEntity

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)
SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flume sensor."""
    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]

    flume_auth = flume_domain_data[FLUME_AUTH]
    http_session = flume_domain_data[FLUME_HTTP_SESSION]
    flume_devices = flume_domain_data[FLUME_DEVICES]

    flume_entity_list = []
    for device in flume_devices.device_list:
        if device[KEY_DEVICE_TYPE] != FLUME_TYPE_SENSOR:
            continue

        device_id = device[KEY_DEVICE_ID]
        device_timezone = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_TIMEZONE]

        coordinator = FlumeDeviceDataUpdateCoordinator(
            hass=hass,
            flume_auth=flume_auth,
            device_id=device_id,
            device_timezone=device_timezone,
            http_session=http_session,
        )

        flume_entity_list.extend(
            [
                FlumeSensor(
                    coordinator=coordinator,
                    description=description,
                    device_id=device_id,
                )
                for description in FLUME_QUERIES_SENSOR
            ]
        )

    if flume_entity_list:
        async_add_entities(flume_entity_list)


class FlumeSensor(FlumeEntity, SensorEntity):
    """Representation of the Flume sensor."""

    coordinator: FlumeDeviceDataUpdateCoordinator

    def __init__(
        self,
        coordinator: FlumeDeviceDataUpdateCoordinator,
        description: SensorEntityDescription,
        device_id: str,
    ) -> None:
        """Inlitializer function with type hints."""
        super().__init__(coordinator, description, device_id)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key
        if sensor_key not in self.coordinator.flume_device.values:
            return None

        return _format_state_value(self.coordinator.flume_device.values[sensor_key])

    async def async_added_to_hass(self) -> None:
        """Request an update when added."""
        await super().async_added_to_hass()
        # We do not ask for an update with async_add_entities()
        # because it will update disabled entities
        await self.coordinator.async_request_refresh()


def _format_state_value(value):
    return round(value, 1) if isinstance(value, Number) else None
