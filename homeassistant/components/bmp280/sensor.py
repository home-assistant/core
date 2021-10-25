"""Platform for Bosch BMP280 Environmental Sensor integration."""
from datetime import timedelta
import logging

from adafruit_bmp280 import Adafruit_BMP280_I2C
import board
from busio import I2C
import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, PRESSURE_HPA, TEMP_CELSIUS
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "BMP280"
SCAN_INTERVAL = timedelta(seconds=15)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)

MIN_I2C_ADDRESS = 0x76
MAX_I2C_ADDRESS = 0x77

CONF_I2C_ADDRESS = "i2c_address"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_I2C_ADDRESS): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_I2C_ADDRESS, max=MAX_I2C_ADDRESS)
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    try:
        # initializing I2C bus using the auto-detected pins
        i2c = I2C(board.SCL, board.SDA)
        # initializing the sensor
        bmp280 = Adafruit_BMP280_I2C(i2c, address=config[CONF_I2C_ADDRESS])
    except ValueError as error:
        # this usually happens when the board is I2C capable, but the device can't be found at the configured address
        if str(error.args[0]).startswith("No I2C device at address"):
            _LOGGER.error(
                "%s. Hint: Check wiring and make sure that the SDO pin is tied to either ground (0x76) or VCC (0x77)",
                error.args[0],
            )
            raise PlatformNotReady() from error
        _LOGGER.error(error)
        return
    # use custom name if there's any
    name = config[CONF_NAME]
    # BMP280 has both temperature and pressure sensing capability
    add_entities(
        [Bmp280TemperatureSensor(bmp280, name), Bmp280PressureSensor(bmp280, name)]
    )


class Bmp280Sensor(SensorEntity):
    """Base class for BMP280 entities."""

    def __init__(
        self,
        bmp280: Adafruit_BMP280_I2C,
        name: str,
        unit_of_measurement: str,
        device_class: str,
    ) -> None:
        """Initialize the sensor."""
        self._bmp280 = bmp280
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit_of_measurement


class Bmp280TemperatureSensor(Bmp280Sensor):
    """Representation of a Bosch BMP280 Temperature Sensor."""

    def __init__(self, bmp280: Adafruit_BMP280_I2C, name: str) -> None:
        """Initialize the entity."""
        super().__init__(
            bmp280, f"{name} Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._attr_native_value = round(self._bmp280.temperature, 1)
            if not self.available:
                _LOGGER.warning("Communication restored with temperature sensor")
                self._attr_available = True
        except OSError:
            # this is thrown when a working sensor is unplugged between two updates
            _LOGGER.warning(
                "Unable to read temperature data due to a communication problem"
            )
            self._attr_available = False


class Bmp280PressureSensor(Bmp280Sensor):
    """Representation of a Bosch BMP280 Barometric Pressure Sensor."""

    def __init__(self, bmp280: Adafruit_BMP280_I2C, name: str) -> None:
        """Initialize the entity."""
        super().__init__(
            bmp280, f"{name} Pressure", PRESSURE_HPA, DEVICE_CLASS_PRESSURE
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._attr_native_value = round(self._bmp280.pressure)
            if not self.available:
                _LOGGER.warning("Communication restored with pressure sensor")
                self._attr_available = True
        except OSError:
            # this is thrown when a working sensor is unplugged between two updates
            _LOGGER.warning(
                "Unable to read pressure data due to a communication problem"
            )
            self._attr_available = False
