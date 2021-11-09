"""Support for BME680 Sensor over SMBus."""
from __future__ import annotations

import logging
import threading
from time import monotonic, sleep

import bme680  # pylint: disable=import-error
from smbus import SMBus
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = "i2c_address"
CONF_I2C_BUS = "i2c_bus"
CONF_OVERSAMPLING_TEMP = "oversampling_temperature"
CONF_OVERSAMPLING_PRES = "oversampling_pressure"
CONF_OVERSAMPLING_HUM = "oversampling_humidity"
CONF_FILTER_SIZE = "filter_size"
CONF_GAS_HEATER_TEMP = "gas_heater_temperature"
CONF_GAS_HEATER_DURATION = "gas_heater_duration"
CONF_AQ_BURN_IN_TIME = "aq_burn_in_time"
CONF_AQ_HUM_BASELINE = "aq_humidity_baseline"
CONF_AQ_HUM_WEIGHTING = "aq_humidity_bias"
CONF_TEMP_OFFSET = "temp_offset"


DEFAULT_NAME = "BME680 Sensor"
DEFAULT_I2C_ADDRESS = 0x77
DEFAULT_I2C_BUS = 1
DEFAULT_OVERSAMPLING_TEMP = 8  # Temperature oversampling x 8
DEFAULT_OVERSAMPLING_PRES = 4  # Pressure oversampling x 4
DEFAULT_OVERSAMPLING_HUM = 2  # Humidity oversampling x 2
DEFAULT_FILTER_SIZE = 3  # IIR Filter Size
DEFAULT_GAS_HEATER_TEMP = 320  # Temperature in celsius 200 - 400
DEFAULT_GAS_HEATER_DURATION = 150  # Heater duration in ms 1 - 4032
DEFAULT_AQ_BURN_IN_TIME = 300  # 300 second burn in time for AQ gas measurement
DEFAULT_AQ_HUM_BASELINE = 40  # 40%, an optimal indoor humidity.
DEFAULT_AQ_HUM_WEIGHTING = 25  # 25% Weighting of humidity to gas in AQ score
DEFAULT_TEMP_OFFSET = 0  # No calibration out of the box.

SENSOR_TEMP = "temperature"
SENSOR_HUMID = "humidity"
SENSOR_PRESS = "pressure"
SENSOR_GAS = "gas"
SENSOR_AQ = "airquality"
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TEMP,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=SENSOR_HUMID,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=SENSOR_PRESS,
        name="Pressure",
        native_unit_of_measurement="mb",
        device_class=DEVICE_CLASS_PRESSURE,
    ),
    SensorEntityDescription(
        key=SENSOR_GAS,
        name="Gas Resistance",
        native_unit_of_measurement="Ohms",
    ),
    SensorEntityDescription(
        key=SENSOR_AQ,
        name="Air Quality",
        native_unit_of_measurement=PERCENTAGE,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]
DEFAULT_MONITORED = [SENSOR_TEMP, SENSOR_HUMID, SENSOR_PRESS, SENSOR_AQ]
OVERSAMPLING_VALUES = {0, 1, 2, 4, 8, 16}
FILTER_VALUES = {0, 1, 3, 7, 15, 31, 63, 127}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): cv.positive_int,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): cv.positive_int,
        vol.Optional(
            CONF_OVERSAMPLING_TEMP, default=DEFAULT_OVERSAMPLING_TEMP
        ): vol.All(vol.Coerce(int), vol.In(OVERSAMPLING_VALUES)),
        vol.Optional(
            CONF_OVERSAMPLING_PRES, default=DEFAULT_OVERSAMPLING_PRES
        ): vol.All(vol.Coerce(int), vol.In(OVERSAMPLING_VALUES)),
        vol.Optional(CONF_OVERSAMPLING_HUM, default=DEFAULT_OVERSAMPLING_HUM): vol.All(
            vol.Coerce(int), vol.In(OVERSAMPLING_VALUES)
        ),
        vol.Optional(CONF_FILTER_SIZE, default=DEFAULT_FILTER_SIZE): vol.All(
            vol.Coerce(int), vol.In(FILTER_VALUES)
        ),
        vol.Optional(CONF_GAS_HEATER_TEMP, default=DEFAULT_GAS_HEATER_TEMP): vol.All(
            vol.Coerce(int), vol.Range(200, 400)
        ),
        vol.Optional(
            CONF_GAS_HEATER_DURATION, default=DEFAULT_GAS_HEATER_DURATION
        ): vol.All(vol.Coerce(int), vol.Range(1, 4032)),
        vol.Optional(
            CONF_AQ_BURN_IN_TIME, default=DEFAULT_AQ_BURN_IN_TIME
        ): cv.positive_int,
        vol.Optional(CONF_AQ_HUM_BASELINE, default=DEFAULT_AQ_HUM_BASELINE): vol.All(
            vol.Coerce(int), vol.Range(1, 100)
        ),
        vol.Optional(CONF_AQ_HUM_WEIGHTING, default=DEFAULT_AQ_HUM_WEIGHTING): vol.All(
            vol.Coerce(int), vol.Range(1, 100)
        ),
        vol.Optional(CONF_TEMP_OFFSET, default=DEFAULT_TEMP_OFFSET): vol.All(
            vol.Coerce(float), vol.Range(-100.0, 100.0)
        ),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the BME680 sensor."""
    name = config[CONF_NAME]

    sensor_handler = await hass.async_add_executor_job(_setup_bme680, config)
    if sensor_handler is None:
        return

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        BME680Sensor(sensor_handler, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    async_add_entities(entities)


def _setup_bme680(config):
    """Set up and configure the BME680 sensor."""

    sensor_handler = None
    sensor = None
    try:
        i2c_address = config[CONF_I2C_ADDRESS]
        bus = SMBus(config[CONF_I2C_BUS])
        sensor = bme680.BME680(i2c_address, bus)

        # Configure Oversampling
        os_lookup = {
            0: bme680.OS_NONE,
            1: bme680.OS_1X,
            2: bme680.OS_2X,
            4: bme680.OS_4X,
            8: bme680.OS_8X,
            16: bme680.OS_16X,
        }
        sensor.set_temperature_oversample(os_lookup[config[CONF_OVERSAMPLING_TEMP]])
        sensor.set_temp_offset(config[CONF_TEMP_OFFSET])
        sensor.set_humidity_oversample(os_lookup[config[CONF_OVERSAMPLING_HUM]])
        sensor.set_pressure_oversample(os_lookup[config[CONF_OVERSAMPLING_PRES]])

        # Configure IIR Filter
        filter_lookup = {
            0: bme680.FILTER_SIZE_0,
            1: bme680.FILTER_SIZE_1,
            3: bme680.FILTER_SIZE_3,
            7: bme680.FILTER_SIZE_7,
            15: bme680.FILTER_SIZE_15,
            31: bme680.FILTER_SIZE_31,
            63: bme680.FILTER_SIZE_63,
            127: bme680.FILTER_SIZE_127,
        }
        sensor.set_filter(filter_lookup[config[CONF_FILTER_SIZE]])

        # Configure the Gas Heater
        if (
            SENSOR_GAS in config[CONF_MONITORED_CONDITIONS]
            or SENSOR_AQ in config[CONF_MONITORED_CONDITIONS]
        ):
            sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
            sensor.set_gas_heater_duration(config[CONF_GAS_HEATER_DURATION])
            sensor.set_gas_heater_temperature(config[CONF_GAS_HEATER_TEMP])
            sensor.select_gas_heater_profile(0)
        else:
            sensor.set_gas_status(bme680.DISABLE_GAS_MEAS)
    except (RuntimeError, OSError):
        _LOGGER.error("BME680 sensor not detected at 0x%02x", i2c_address)
        return None

    sensor_handler = BME680Handler(
        sensor,
        (
            SENSOR_GAS in config[CONF_MONITORED_CONDITIONS]
            or SENSOR_AQ in config[CONF_MONITORED_CONDITIONS]
        ),
        config[CONF_AQ_BURN_IN_TIME],
        config[CONF_AQ_HUM_BASELINE],
        config[CONF_AQ_HUM_WEIGHTING],
    )
    sleep(0.5)  # Wait for device to stabilize
    if not sensor_handler.sensor_data.temperature:
        _LOGGER.error("BME680 sensor failed to Initialize")
        return None

    return sensor_handler


class BME680Handler:
    """BME680 sensor working in i2C bus."""

    class SensorData:
        """Sensor data representation."""

        def __init__(self):
            """Initialize the sensor data object."""
            self.temperature = None
            self.humidity = None
            self.pressure = None
            self.gas_resistance = None
            self.air_quality = None

    def __init__(
        self,
        sensor,
        gas_measurement=False,
        burn_in_time=300,
        hum_baseline=40,
        hum_weighting=25,
    ):
        """Initialize the sensor handler."""
        self.sensor_data = BME680Handler.SensorData()
        self._sensor = sensor
        self._gas_sensor_running = False
        self._hum_baseline = hum_baseline
        self._hum_weighting = hum_weighting
        self._gas_baseline = None

        if gas_measurement:

            threading.Thread(
                target=self._run_gas_sensor,
                kwargs={"burn_in_time": burn_in_time},
                name="BME680Handler_run_gas_sensor",
            ).start()
        self.update(first_read=True)

    def _run_gas_sensor(self, burn_in_time):
        """Calibrate the Air Quality Gas Baseline."""
        if self._gas_sensor_running:
            return

        self._gas_sensor_running = True

        # Pause to allow initial data read for device validation.
        sleep(1)

        start_time = monotonic()
        curr_time = monotonic()
        burn_in_data = []

        _LOGGER.info(
            "Beginning %d second gas sensor burn in for Air Quality", burn_in_time
        )
        while curr_time - start_time < burn_in_time:
            curr_time = monotonic()
            if self._sensor.get_sensor_data() and self._sensor.data.heat_stable:
                gas_resistance = self._sensor.data.gas_resistance
                burn_in_data.append(gas_resistance)
                self.sensor_data.gas_resistance = gas_resistance
                _LOGGER.debug(
                    "AQ Gas Resistance Baseline reading %2f Ohms", gas_resistance
                )
                sleep(1)

        _LOGGER.debug(
            "AQ Gas Resistance Burn In Data (Size: %d): \n\t%s",
            len(burn_in_data),
            burn_in_data,
        )
        self._gas_baseline = sum(burn_in_data[-50:]) / 50.0
        _LOGGER.info("Completed gas sensor burn in for Air Quality")
        _LOGGER.info("AQ Gas Resistance Baseline: %f", self._gas_baseline)
        while True:
            if self._sensor.get_sensor_data() and self._sensor.data.heat_stable:
                self.sensor_data.gas_resistance = self._sensor.data.gas_resistance
                self.sensor_data.air_quality = self._calculate_aq_score()
                sleep(1)

    def update(self, first_read=False):
        """Read sensor data."""
        if first_read:
            # Attempt first read, it almost always fails first attempt
            self._sensor.get_sensor_data()
        if self._sensor.get_sensor_data():
            self.sensor_data.temperature = self._sensor.data.temperature
            self.sensor_data.humidity = self._sensor.data.humidity
            self.sensor_data.pressure = self._sensor.data.pressure

    def _calculate_aq_score(self):
        """Calculate the Air Quality Score."""
        hum_baseline = self._hum_baseline
        hum_weighting = self._hum_weighting
        gas_baseline = self._gas_baseline

        gas_resistance = self.sensor_data.gas_resistance
        gas_offset = gas_baseline - gas_resistance

        hum = self.sensor_data.humidity
        hum_offset = hum - hum_baseline

        # Calculate hum_score as the distance from the hum_baseline.
        if hum_offset > 0:
            hum_score = (
                (100 - hum_baseline - hum_offset) / (100 - hum_baseline) * hum_weighting
            )
        else:
            hum_score = (hum_baseline + hum_offset) / hum_baseline * hum_weighting

        # Calculate gas_score as the distance from the gas_baseline.
        if gas_offset > 0:
            gas_score = (gas_resistance / gas_baseline) * (100 - hum_weighting)
        else:
            gas_score = 100 - hum_weighting

        # Calculate air quality score.
        return hum_score + gas_score


class BME680Sensor(SensorEntity):
    """Implementation of the BME680 sensor."""

    def __init__(self, bme680_client, name, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self.bme680_client = bme680_client

    async def async_update(self):
        """Get the latest data from the BME680 and update the states."""
        await self.hass.async_add_executor_job(self.bme680_client.update)
        sensor_type = self.entity_description.key
        if sensor_type == SENSOR_TEMP:
            self._attr_native_value = round(
                self.bme680_client.sensor_data.temperature, 1
            )
        elif sensor_type == SENSOR_HUMID:
            self._attr_native_value = round(self.bme680_client.sensor_data.humidity, 1)
        elif sensor_type == SENSOR_PRESS:
            self._attr_native_value = round(self.bme680_client.sensor_data.pressure, 1)
        elif sensor_type == SENSOR_GAS:
            self._attr_native_value = int(
                round(self.bme680_client.sensor_data.gas_resistance, 0)
            )
        elif sensor_type == SENSOR_AQ:
            aq_score = self.bme680_client.sensor_data.air_quality
            if aq_score is not None:
                self._attr_native_value = round(aq_score, 1)
