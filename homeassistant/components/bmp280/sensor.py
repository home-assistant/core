"""Platform for Bosch BMP280 Environmental Sensor integration."""
import logging

from adafruit_bmp280 import Adafruit_BMP280_I2C
import busio
import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PLATFORM_SCHEMA,
)
from homeassistant.const import CONF_NAME, PRESSURE_HPA, TEMP_CELSIUS
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "BMP280"
DEFAULT_I2C_ADDRESS = 0x77

MIN_I2C_ADDRESS = 0x76
MAX_I2C_ADDRESS = 0x77

CONF_I2C_ADDRESS = "i2c_address"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_I2C_ADDRESS, max=MAX_I2C_ADDRESS)
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    try:
        # this throws an exception if board is not supported
        import board

        # initializing I2C bus using the auto-detected pins
        i2c = busio.I2C(board.SCL, board.SDA)
        # initializing the sensor
        bmp280 = Adafruit_BMP280_I2C(i2c, address=config.get(CONF_I2C_ADDRESS))
        # use custom name if there's any
        name = config.get(CONF_NAME)
        # BMP280 has both temperature and pressure sensing capability
        add_entities(
            [Bmp280TemperatureSensor(bmp280, name), Bmp280PressureSensor(bmp280, name)]
        )
    except NotImplementedError as error:
        # this is thrown right after the import statement if the board is unsupported
        if error.args[0] == "Board not supported":
            _LOGGER.error(
                "Failed to determine board type. Is this instance running on a Raspberry Pi or a similar I2C capable device?"
            )
            raise PlatformNotReady()
        raise error
    except ValueError as error:
        # this happens when the board is I2C capable, but the device is not found at the configured address
        if str(error.args[0]).startswith("No I2C device at address"):
            _LOGGER.error(error.args[0])
            raise PlatformNotReady()
        raise error


class Bmp280Sensor(Entity):
    """Base class for BMP280 entities."""

    errored = False

    def __init__(
        self,
        bmp280: Adafruit_BMP280_I2C,
        name: str,
        unit_of_measurement: str,
        device_class: str,
    ):
        """Initialize the sensor."""
        self._bmp280 = bmp280
        self._name = name
        self._unit_of_measurement = unit_of_measurement
        self._device_class = device_class
        self._state = None
        self._errored = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return if the device is currently available."""
        return not Bmp280Sensor.errored


class Bmp280TemperatureSensor(Bmp280Sensor):
    """Representation of a Bosch BMP280 Temperature Sensor."""

    def __init__(self, bmp280: Adafruit_BMP280_I2C, name: str):
        """Initialize the entity."""
        super().__init__(
            bmp280, f"{name} Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE
        )

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._state = round(self._bmp280.temperature, 1)
            if Bmp280Sensor.errored:
                _LOGGER.warning("Communication restored with temperature sensor")
                Bmp280Sensor.errored = False
        except OSError:
            # this is thrown when a working sensor is unplugged between two updates
            _LOGGER.warning(
                "Unable to read temperature data due to a communication problem"
            )
            Bmp280Sensor.errored = True


class Bmp280PressureSensor(Bmp280Sensor):
    """Representation of a Bosch BMP280 Barometric Pressure Sensor."""

    def __init__(self, bmp280: Adafruit_BMP280_I2C, name: str):
        """Initialize the entity."""
        super().__init__(
            bmp280, f"{name} Pressure", PRESSURE_HPA, DEVICE_CLASS_PRESSURE
        )

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._state = round(self._bmp280.pressure)
            if Bmp280Sensor.errored:
                _LOGGER.warning("Communication restored with pressure sensor")
                Bmp280Sensor.errored = False
        except OSError:
            # this is thrown when a working sensor is unplugged between two updates
            _LOGGER.warning(
                "Unable to read pressure data due to a communication problem"
            )
            Bmp280Sensor.errored = True
