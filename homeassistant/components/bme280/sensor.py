"""Support for BME280 temperature, humidity and pressure sensor."""
from contextlib import suppress
from functools import partial
import logging

from bme280spi import BME280 as BME280_spi  # pylint: disable=import-error
from i2csense.bme280 import BME280 as BME280_i2c  # pylint: disable=import-error
import smbus

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import Throttle
from homeassistant.util.temperature import celsius_to_fahrenheit

from .const import (
    CONF_DELTA_TEMP,
    CONF_FILTER_MODE,
    CONF_I2C_ADDRESS,
    CONF_I2C_BUS,
    CONF_OPERATION_MODE,
    CONF_OVERSAMPLING_HUM,
    CONF_OVERSAMPLING_PRES,
    CONF_OVERSAMPLING_TEMP,
    CONF_SPI_BUS,
    CONF_SPI_DEV,
    CONF_T_STANDBY,
    DOMAIN,
    INTERFACE_I2C,
    INTERFACE_SPI,
    MIN_TIME_BETWEEN_UPDATES,
    SENSOR_HUMID,
    SENSOR_PRESS,
    SENSOR_TEMP,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the BME280 sensor."""
    if discovery_info is None:
        return
    SENSOR_TYPES[SENSOR_TEMP][1] = hass.config.units.temperature_unit
    sensor_conf = discovery_info[SENSOR_DOMAIN]
    name = sensor_conf[CONF_NAME]
    scan_interval = sensor_conf[CONF_SCAN_INTERVAL]
    if CONF_SPI_BUS in sensor_conf and CONF_SPI_DEV in sensor_conf:
        spi_dev = sensor_conf[CONF_SPI_DEV]
        spi_bus = sensor_conf[CONF_SPI_BUS]
        _LOGGER.debug("BME280 sensor initialize at %s.%s", spi_bus, spi_dev)
        interface = INTERFACE_SPI
        sensor = await hass.async_add_executor_job(
            partial(
                BME280_spi,
                t_mode=sensor_conf[CONF_OVERSAMPLING_TEMP],
                p_mode=sensor_conf[CONF_OVERSAMPLING_PRES],
                h_mode=sensor_conf[CONF_OVERSAMPLING_HUM],
                standby=sensor_conf[CONF_T_STANDBY],
                filter=sensor_conf[CONF_FILTER_MODE],
                spi_bus=sensor_conf[CONF_SPI_BUS],
                spi_dev=sensor_conf[CONF_SPI_DEV],
            )
        )
        if not sensor.sample_ok:
            _LOGGER.error("BME280 sensor not detected at %s.%s", spi_bus, spi_dev)
            return
        sensor_update = sensor.update
    else:
        i2c_address = sensor_conf[CONF_I2C_ADDRESS]
        bus = smbus.SMBus(sensor_conf[CONF_I2C_BUS])
        interface = INTERFACE_I2C
        sensor = await hass.async_add_executor_job(
            partial(
                BME280_i2c,
                bus,
                i2c_address,
                osrs_t=sensor_conf[CONF_OVERSAMPLING_TEMP],
                osrs_p=sensor_conf[CONF_OVERSAMPLING_PRES],
                osrs_h=sensor_conf[CONF_OVERSAMPLING_HUM],
                mode=sensor_conf[CONF_OPERATION_MODE],
                t_sb=sensor_conf[CONF_T_STANDBY],
                filter_mode=sensor_conf[CONF_FILTER_MODE],
                delta_temp=sensor_conf[CONF_DELTA_TEMP],
            )
        )
        if not sensor.sample_ok:
            _LOGGER.error("BME280 sensor not detected at %s", i2c_address)
            return
        sensor_update = partial(sensor.update, True)
    await hass.async_add_executor_job(sensor_update)
    sensor_handler = BME280Handler(sensor, interface)
    entities = []
    with suppress(KeyError):
        for condition in sensor_conf[CONF_MONITORED_CONDITIONS]:
            entities.append(
                BME280Sensor(
                    hass,
                    sensor_handler,
                    condition,
                    SENSOR_TYPES[condition][1],
                    name,
                    scan_interval,
                )
            )
    async_add_entities(entities, True)


class BME280Handler:
    """BME280 sensor working in SPI or I2C bus."""

    def __init__(self, sensor, interface):
        """Initialize the sensor handler."""
        self.sensor = sensor
        self.interface = interface
        if self.interface == INTERFACE_SPI:
            self.update = self.update_spi
        elif self.interface == INTERFACE_I2C:
            self.update = self.update_i2c

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_spi(self):
        """Read sensor data."""
        self.sensor.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_i2c(self, first_reading=False):
        """Read sensor data."""
        self.sensor.update(first_reading)


class BME280Sensor(CoordinatorEntity, SensorEntity):
    """Implementation of the BME280 sensor."""

    def __init__(
        self, hass, bme280_client, sensor_type, temp_unit, name, scan_interval
    ):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.bme280_client = bme280_client
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        super().__init__(
            DataUpdateCoordinator(
                hass,
                _LOGGER,
                name=DOMAIN,
                update_method=self.async_update,
                update_interval=scan_interval,
            )
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data from the BME280 and update the states."""
        await self.hass.async_add_executor_job(self.bme280_client.update)
        if self.bme280_client.sensor.sample_ok:
            if self.type == SENSOR_TEMP:
                temperature = round(self.bme280_client.sensor.temperature, 1)
                if self.temp_unit == TEMP_FAHRENHEIT:
                    temperature = round(celsius_to_fahrenheit(temperature), 1)
                self._state = temperature
            elif self.type == SENSOR_HUMID:
                self._state = round(self.bme280_client.sensor.humidity, 1)
            elif self.type == SENSOR_PRESS:
                self._state = round(self.bme280_client.sensor.pressure, 1)
        else:
            _LOGGER.warning("Bad update of sensor.%s", self.name)
