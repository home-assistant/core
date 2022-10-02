"""Sensor for displaying the number of result from Flume."""
from numbers import Number

from pyflume import FlumeData

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_SCAN_INTERVAL,
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
        if (
            device[KEY_DEVICE_TYPE] != FLUME_TYPE_SENSOR
            or KEY_DEVICE_LOCATION not in device
        ):
            continue

        device_id = device[KEY_DEVICE_ID]
        device_timezone = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_TIMEZONE]

        flume_device = FlumeData(
            flume_auth,
            device_id,
            device_timezone,
            scan_interval=DEVICE_SCAN_INTERVAL,
            update_on_init=False,
            http_session=http_session,
        )

        coordinator = FlumeDeviceDataUpdateCoordinator(
            hass=hass, flume_device=flume_device
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
        device_id: str,
        description: SensorEntityDescription,
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


def _format_state_value(value):
    return round(value, 1) if isinstance(value, Number) else None
