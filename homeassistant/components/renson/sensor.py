"""Sensor data of the Renson ventilation unit."""
from dataclasses import dataclass
from datetime import timedelta
import logging

import async_timeout
from renson_endura_delta.field_enum import (
    AIR_QUALITY_FIELD,
    BREEZE_LEVEL_FIELD,
    BREEZE_TEMPERATURE_FIELD,
    BYPASS_LEVEL_FIELD,
    BYPASS_TEMPERATURE_FIELD,
    CO2_FIELD,
    CO2_HYSTERESIS_FIELD,
    CO2_QUALITY_FIELD,
    CO2_THRESHOLD_FIELD,
    CURRENT_AIRFLOW_EXTRACT_FIELD,
    CURRENT_AIRFLOW_INGOING_FIELD,
    CURRENT_LEVEL_FIELD,
    DAY_POLLUTION_FIELD,
    DAYTIME_FIELD,
    FILTER_PRESET_FIELD,
    FILTER_REMAIN_FIELD,
    HUMIDITY_FIELD,
    INDOOR_TEMP_FIELD,
    MANUAL_LEVEL_FIELD,
    NIGHT_POLLUTION_FIELD,
    NIGHTTIME_FIELD,
    OUTDOOR_TEMP_FIELD,
    FieldEnum,
)
from renson_endura_delta.renson import RensonVentilation
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONCENTRATION_PARTS_PER_CUBIC_METER, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST, default=[]): cv.string}
)


@dataclass
class RensonSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    field: FieldEnum
    raw_format: bool


@dataclass
class RensonSensorEntityDescription(
    SensorEntityDescription, RensonSensorEntityDescriptionMixin
):
    """Description of sensor."""


SENSORS: tuple[RensonSensorEntityDescription, ...] = (
    RensonSensorEntityDescription(
        key="CO2_QUALITY_FIELD",
        name="CO2 quality",
        field=CO2_QUALITY_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RensonSensorEntityDescription(
        key="AIR_QUALITY_FIELD",
        name="Air quality",
        field=AIR_QUALITY_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RensonSensorEntityDescription(
        key="CO2_FIELD",
        name="CO2 quality value",
        field=CO2_FIELD,
        raw_format=True,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
    ),
    RensonSensorEntityDescription(
        key="AIR_FIELD",
        name="Air quality value",
        field=AIR_QUALITY_FIELD,
        state_class=SensorStateClass.MEASUREMENT,
        raw_format=True,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
    ),
    RensonSensorEntityDescription(
        key="CURRENT_LEVEL_FIELD_RAW",
        name="Ventilation level raw",
        field=CURRENT_LEVEL_FIELD,
        state_class=SensorStateClass.MEASUREMENT,
        raw_format=True,
    ),
    RensonSensorEntityDescription(
        key="CURRENT_LEVEL_FIELD",
        name="Ventilation level",
        state_class=SensorStateClass.MEASUREMENT,
        field=CURRENT_LEVEL_FIELD,
        raw_format=False,
    ),
    RensonSensorEntityDescription(
        key="CURRENT_AIRFLOW_EXTRACT_FIELD",
        name="Total airflow out",
        field=CURRENT_AIRFLOW_EXTRACT_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m³/h",
    ),
    RensonSensorEntityDescription(
        key="CURRENT_AIRFLOW_INGOING_FIELD",
        name="Total airflow in",
        field=CURRENT_AIRFLOW_INGOING_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m³/h",
    ),
    RensonSensorEntityDescription(
        key="OUTDOOR_TEMP_FIELD",
        name="Outdoor air temperature",
        field=OUTDOOR_TEMP_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="INDOOR_TEMP_FIELD",
        name="Extract air temperature",
        field=INDOOR_TEMP_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="FILTER_REMAIN_FIELD",
        name="Filter change",
        field=FILTER_REMAIN_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="days",
    ),
    RensonSensorEntityDescription(
        key="HUMIDITY_FIELD",
        name="Relative humidity",
        field=HUMIDITY_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RensonSensorEntityDescription(
        key="MANUAL_LEVEL_FIELD",
        name="Manual level",
        field=MANUAL_LEVEL_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RensonSensorEntityDescription(
        key="BREEZE_TEMPERATURE_FIELD",
        name="Breeze temperature",
        field=BREEZE_TEMPERATURE_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="BREEZE_LEVEL_FIELD",
        name="Breeze level",
        field=BREEZE_LEVEL_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="DAYTIME_FIELD",
        name="Start day time",
        field=DAYTIME_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="NIGHTTIME_FIELD",
        name="Start night time",
        field=NIGHTTIME_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="DAY_POLLUTION_FIELD",
        name="Day pollution level",
        field=DAY_POLLUTION_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="NIGHT_POLLUTION_FIELD",
        name="Night pollution level",
        field=NIGHT_POLLUTION_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="CO2_THRESHOLD_FIELD",
        name="CO2 threshold",
        field=CO2_THRESHOLD_FIELD,
        raw_format=False,
        native_unit_of_measurement="ppm",
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="CO2_HYSTERESIS_FIELD",
        name="CO2 hysteresis",
        field=CO2_HYSTERESIS_FIELD,
        raw_format=False,
        native_unit_of_measurement="ppm",
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="BYPASS_TEMPERATURE_FIELD",
        name="Bypass activation temperature",
        field=BYPASS_TEMPERATURE_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="BYPASS_LEVEL_FIELD",
        name="Bypass level",
        field=BYPASS_LEVEL_FIELD,
        raw_format=False,
        device_class="power_factor",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RensonSensorEntityDescription(
        key="FILTER_PRESET_FIELD",
        name="Filter preset time",
        field=FILTER_PRESET_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="days",
    ),
)


class RensonCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, api):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Renson sensor",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(30):
                return await self.hass.async_add_executor_job(self.api.get_all_data)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class RensonSensor(CoordinatorEntity, SensorEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        description: RensonSensorEntityDescription,
        renson_api: RensonVentilation,
        coordinator: RensonCoordinator,
    ) -> None:
        """Initialize class."""
        super().__init__(coordinator)

        self._state = None
        self.entity_description = description
        self.field = description.field
        self.data_type = description.field.field_type
        self.renson_api = renson_api
        self.raw_format = description.raw_format

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        all_data = self.coordinator.data

        value = self.renson_api.get_field_value(all_data, self.field.name)

        if self.raw_format:
            self._state = value
        else:
            self._state = self.renson_api.parse_value(value, self.data_type)

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Call the Renson integration to setup."""

    renson_api: RensonVentilation = hass.data[DOMAIN][config.entry_id]

    coordinator = RensonCoordinator(hass, renson_api)

    entities: list = []
    for description in SENSORS:
        entities.append(RensonSensor(description, renson_api, coordinator))
    async_add_entities(entities)
    await coordinator.async_config_entry_first_refresh()
