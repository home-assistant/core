"""Sensor for displaying the number of result from Flume."""

from typing import Any

from pyflume import FlumeAuth, FlumeData
from requests import Session

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DEVICE_SCAN_INTERVAL,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_NAME,
    KEY_DEVICE_LOCATION_TIMEZONE,
    KEY_DEVICE_TYPE,
)
from .coordinator import FlumeConfigEntry, FlumeDeviceDataUpdateCoordinator
from .entity import FlumeEntity
from .util import get_valid_flume_devices

FLUME_QUERIES_SENSOR: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="current_interval",
        translation_key="current_interval",
        suggested_display_precision=2,
        native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/m",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="month_to_date",
        translation_key="month_to_date",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="week_to_date",
        translation_key="week_to_date",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="today",
        translation_key="today",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="last_60_min",
        translation_key="last_60_min",
        suggested_display_precision=2,
        native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/h",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="last_24_hrs",
        translation_key="last_24_hrs",
        suggested_display_precision=2,
        native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/d",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="last_30_days",
        translation_key="last_30_days",
        suggested_display_precision=2,
        native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/mo",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


def make_flume_datas(
    http_session: Session, flume_auth: FlumeAuth, flume_devices: list[dict[str, Any]]
) -> dict[str, FlumeData]:
    """Create FlumeData objects for each device."""
    flume_datas: dict[str, FlumeData] = {}
    for device in flume_devices:
        device_id = device[KEY_DEVICE_ID]
        device_timezone = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_TIMEZONE]
        flume_data = FlumeData(
            flume_auth,
            device_id,
            device_timezone,
            scan_interval=DEVICE_SCAN_INTERVAL,
            update_on_init=False,
            http_session=http_session,
        )
        flume_datas[device_id] = flume_data
    return flume_datas


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlumeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flume sensor."""

    flume_domain_data = config_entry.runtime_data
    flume_devices = flume_domain_data.devices
    flume_auth = flume_domain_data.auth
    http_session = flume_domain_data.http_session
    flume_devices = [
        device
        for device in get_valid_flume_devices(flume_devices)
        if device[KEY_DEVICE_TYPE] == FLUME_TYPE_SENSOR
    ]
    flume_entity_list: list[FlumeSensor] = []
    flume_datas = await hass.async_add_executor_job(
        make_flume_datas, http_session, flume_auth, flume_devices
    )

    for device in flume_devices:
        device_id: str = device[KEY_DEVICE_ID]
        device_location_name = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_NAME]
        flume_device = flume_datas[device_id]

        coordinator = FlumeDeviceDataUpdateCoordinator(
            hass=hass, config_entry=config_entry, flume_device=flume_device
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
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key
        if sensor_key not in self.coordinator.flume_device.values:
            return None

        return self.coordinator.flume_device.values[sensor_key]
