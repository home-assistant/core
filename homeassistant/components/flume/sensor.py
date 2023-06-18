"""Sensor for displaying the number of result from Flume."""
from numbers import Number

from pyflume import FlumeData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_NAME,
    KEY_DEVICE_LOCATION_TIMEZONE,
    KEY_DEVICE_TYPE,
)
from .coordinator import FlumeDeviceDataUpdateCoordinator
from .entity import FlumeEntity
from .util import get_valid_flume_devices

FLUME_QUERIES_SENSOR: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="current_interval",
        name="Current",
        native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/m",
    ),
    SensorEntityDescription(
        key="month_to_date",
        name="Current Month",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="week_to_date",
        name="Current Week",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="today",
        name="Current Day",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="last_60_min",
        name="60 Minutes",
        native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/h",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="last_24_hrs",
        name="24 Hours",
        native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/d",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="last_30_days",
        name="30 Days",
        native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/mo",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flume sensor."""

    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]
    flume_devices = flume_domain_data[FLUME_DEVICES]
    flume_auth = flume_domain_data[FLUME_AUTH]
    http_session = flume_domain_data[FLUME_HTTP_SESSION]
    flume_devices = [
        device
        for device in get_valid_flume_devices(flume_devices)
        if device[KEY_DEVICE_TYPE] == FLUME_TYPE_SENSOR
    ]
    flume_entity_list = []
    for device in flume_devices:
        device_id = device[KEY_DEVICE_ID]
        device_timezone = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_TIMEZONE]
        device_location_name = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_NAME]

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
                    location_name=device_location_name,
                )
                for description in FLUME_QUERIES_SENSOR
            ]
        )

    async_add_entities(flume_entity_list)


class FlumeSensor(FlumeEntity[FlumeDeviceDataUpdateCoordinator], SensorEntity):
    """Representation of the Flume sensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key
        if sensor_key not in self.coordinator.flume_device.values:
            return None

        return _format_state_value(self.coordinator.flume_device.values[sensor_key])


def _format_state_value(value):
    return round(value, 1) if isinstance(value, Number) else None
