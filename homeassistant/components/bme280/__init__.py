"""The bme280 component."""
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.helpers import config_validation as cv, discovery

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
    DEFAULT_DELTA_TEMP,
    DEFAULT_FILTER_MODE,
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DEFAULT_MONITORED,
    DEFAULT_NAME,
    DEFAULT_OPERATION_MODE,
    DEFAULT_OVERSAMPLING_HUM,
    DEFAULT_OVERSAMPLING_PRES,
    DEFAULT_OVERSAMPLING_TEMP,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_T_STANDBY,
    DOMAIN,
    SENSOR_TYPES,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_SPI_BUS): vol.Coerce(int),
                        vol.Optional(CONF_SPI_DEV): vol.Coerce(int),
                        vol.Optional(
                            CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS
                        ): cv.string,
                        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(
                            int
                        ),
                        vol.Optional(
                            CONF_DELTA_TEMP, default=DEFAULT_DELTA_TEMP
                        ): vol.Coerce(float),
                        vol.Optional(
                            CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED
                        ): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
                        vol.Optional(
                            CONF_OVERSAMPLING_TEMP, default=DEFAULT_OVERSAMPLING_TEMP
                        ): vol.Coerce(int),
                        vol.Optional(
                            CONF_OVERSAMPLING_PRES, default=DEFAULT_OVERSAMPLING_PRES
                        ): vol.Coerce(int),
                        vol.Optional(
                            CONF_OVERSAMPLING_HUM, default=DEFAULT_OVERSAMPLING_HUM
                        ): vol.Coerce(int),
                        vol.Optional(
                            CONF_OPERATION_MODE, default=DEFAULT_OPERATION_MODE
                        ): vol.Coerce(int),
                        vol.Optional(
                            CONF_T_STANDBY, default=DEFAULT_T_STANDBY
                        ): vol.Coerce(int),
                        vol.Optional(
                            CONF_FILTER_MODE, default=DEFAULT_FILTER_MODE
                        ): vol.Coerce(int),
                        vol.Optional(
                            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                        ): cv.time_period,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up BME280 component."""
    bme280_config = config[DOMAIN]
    for bme280_conf in bme280_config:
        discovery_info = {SENSOR_DOMAIN: bme280_conf}
        hass.async_create_task(
            discovery.async_load_platform(
                hass, SENSOR_DOMAIN, DOMAIN, discovery_info, config
            )
        )
    return True
