"""Sensor data of the Renson ventilation unit."""
import logging

from rensonVentilationLib.fieldEnum import (
    AIR_QUALITY_CONTROL_FIELD,
    AIR_QUALITY_FIELD,
    BREEZE_ENABLE_FIELD,
    BREEZE_LEVEL_FIELD,
    BREEZE_MET_FIELD,
    BREEZE_TEMPERATURE_FIELD,
    BYPASS_LEVEL_FIELD,
    BYPASS_TEMPERATURE_FIELD,
    CO2_CONTROL_FIELD,
    CO2_FIELD,
    CO2_HYSTERESIS_FIELD,
    CO2_THRESHOLD_FIELD,
    CURRENT_AIRFLOW_EXTRACT_FIELD,
    CURRENT_AIRFLOW_INGOING_FIELD,
    CURRENT_LEVEL_FIELD,
    DAY_POLLUTION_FIELD,
    DAYTIME_FIELD,
    FILTER_PRESET_FIELD,
    FILTER_REMAIN_FIELD,
    FROST_PROTECTION_FIELD,
    HUMIDITY_CONTROL_FIELD,
    HUMIDITY_FIELD,
    INDOOR_TEMP_FIELD,
    MANUAL_LEVEL_FIELD,
    NIGHT_POLLUTION_FIELD,
    NIGHTTIME_FIELD,
    OUTDOOR_TEMP_FIELD,
    PREHEATER_FIELD,
    TIME_AND_DATE_FIELD,
    FieldEnum,
)
import rensonVentilationLib.renson as renson
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DOMAIN = "renson_ventilation"

CONF_HOST = "host"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST, default=[]): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Call the Renson integration to setup."""
    host = config[CONF_HOST]

    async_add_entities(
        [
            SensorValue("CO2", "", "", CO2_FIELD, host, False),
            SensorValue("Air quality", "", "", AIR_QUALITY_FIELD, host, False),
            SensorValue("CO2 value", "carbon_dioxide", "ppm", CO2_FIELD, host, False),
            SensorValue(
                "Air quality value",
                "",
                "ppm",
                AIR_QUALITY_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Ventilation level raw",
                "",
                "",
                CURRENT_LEVEL_FIELD,
                host,
                True,
            ),
            SensorValue("Ventilation level", "", "", CURRENT_LEVEL_FIELD, host, False),
            SensorValue(
                "Total airflow out",
                "",
                "m³/h",
                CURRENT_AIRFLOW_EXTRACT_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Total airflow in",
                "",
                "m³/h",
                CURRENT_AIRFLOW_INGOING_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Outdoor air temperature",
                "temperature",
                TEMP_CELSIUS,
                OUTDOOR_TEMP_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Extract air temperature",
                "temperature",
                TEMP_CELSIUS,
                INDOOR_TEMP_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Filter change",
                "",
                "days",
                FILTER_REMAIN_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Relative humidity",
                "humidity",
                "%",
                HUMIDITY_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Frost protection active",
                "",
                "",
                FROST_PROTECTION_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Manual level",
                "",
                "",
                MANUAL_LEVEL_FIELD,
                host,
                False,
            ),
            SensorValue(
                "System time",
                "timestamp",
                "",
                TIME_AND_DATE_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Breeze temperature",
                "temperature",
                TEMP_CELSIUS,
                BREEZE_TEMPERATURE_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Breeze enabled",
                "",
                "",
                BREEZE_ENABLE_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Breeze level",
                "",
                "",
                BREEZE_LEVEL_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Breeze conditions met",
                "",
                "",
                BREEZE_MET_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Start day time",
                "",
                "",
                DAYTIME_FIELD,
                host,
                False,
            ),
            host,
            SensorValue(
                "Start night time",
                "",
                "",
                NIGHTTIME_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Day pollution level",
                "",
                "",
                DAY_POLLUTION_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Night pollution level",
                "",
                "",
                NIGHT_POLLUTION_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Humidity control enabled",
                "",
                "",
                HUMIDITY_CONTROL_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Air quality control enabled",
                "",
                "",
                AIR_QUALITY_CONTROL_FIELD,
                host,
                False,
            ),
            SensorValue(
                "CO2 control enabled",
                "",
                "",
                CO2_CONTROL_FIELD,
                host,
                False,
            ),
            SensorValue(
                "CO2 threshold",
                "",
                "ppm",
                CO2_THRESHOLD_FIELD,
                host,
                False,
            ),
            SensorValue(
                "CO2 hysteresis",
                "",
                "ppm",
                CO2_HYSTERESIS_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Preheater enabled",
                "",
                "",
                PREHEATER_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Bypass activation temperature",
                "temperature",
                TEMP_CELSIUS,
                BYPASS_TEMPERATURE_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Bypass level",
                "power_factor",
                "%",
                BYPASS_LEVEL_FIELD,
                host,
                False,
            ),
            SensorValue(
                "Filter preset time",
                "",
                "days",
                FILTER_PRESET_FIELD,
                host,
                False,
            ),
            FirmwareSenor(host),
        ]
    )


class FirmwareSenor(Entity):
    """Check firmware update and store it in the state of the class."""

    def __init__(self, host):
        """Initialize class."""
        self._state = None
        self.renson: renson.RensonVentilation = renson.RensonVentilation(host)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Latest firmware"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Get firmware and safe it in state."""
        self._state = await self.renson.is_firmware_up_to_date()


class SensorValue(Entity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        name: str,
        device_class: str,
        unit_of_measurement: str,
        field: FieldEnum,
        host: str,
        rawFormat: bool,
    ):
        """Initialize class."""
        super().__init__()

        self._state = None
        self.sensorName = name
        self.field = field.name
        self.deviceClass = device_class
        self.unitOfMeasurement = unit_of_measurement
        self.dataType = field.field_type
        self.renson: renson.RensonVentilation = renson.RensonVentilation(host)
        self.rawFormat = rawFormat

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.sensorName

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self.deviceClass

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self.unitOfMeasurement

    @property
    def state(self):
        """Lookup the state of the sensor and save it."""
        return self._state

    async def async_update(self):
        """Save state of sensor."""
        if self.rawFormat:
            self._state = await self.renson.get_data_string(self.field)
        else:
            if self.dataType == "numeric":
                self._state = await self.renson.get_data_numeric(self.field)
            elif self.dataType == "string":
                self._state = await self.renson.get_data_string(self.field)
            elif self.dataType == "level":
                self._state = await self.renson.get_data_level(self.field)
            elif self.dataType == "boolean":
                self._state = await self.renson.get_data_boolean(self.field)
            elif self.dataType == "quality":
                self._state = await self.renson.get_data_quality(self.field)
