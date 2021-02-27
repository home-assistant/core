"""Support for Modbus Holding Register bit sensors."""
import logging
from typing import Optional

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SLAVE,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_ON,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

from .const import CONF_BIT_NUMBER, CONF_BIT_SENSORS, CONF_COUNT, MODBUS_DOMAIN
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities,
    discovery_info: Optional[DiscoveryInfoType] = None,
):
    """Set up the Modbus sensors."""
    sensors = []

    _LOGGER.error("*** bit sensor 1, %s", discovery_info)
    #  check for old config:
    if discovery_info is None:
        return

    _LOGGER.error("*** bit sensor 2")

    for entry in discovery_info[CONF_BIT_SENSORS]:

        _LOGGER.error("*** bit sensor 3, %s", entry)

        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]

        words_count = int(entry[CONF_COUNT])
        bit_number = int(entry[CONF_BIT_NUMBER])

        if bit_number >= words_count * 16:
            _LOGGER.error(
                "Bit number for the %s sensor is out of range",
                entry[CONF_NAME],
            )

        sensors.append(
            ModbusBitSensor(
                hub,
                entry[CONF_NAME],
                entry.get(CONF_SLAVE),
                entry[CONF_ADDRESS],
                bit_number,
                entry.get(CONF_UNIT_OF_MEASUREMENT),
                words_count,
                entry.get(CONF_DEVICE_CLASS),
            )
        )

    if not sensors:
        return False
    async_add_entities(sensors)


class ModbusBitSensor(RestoreEntity):
    """Modbus bit sensor."""

    def __init__(
        self,
        hub,
        name,
        slave,
        register,
        bit_number,
        unit_of_measurement,
        count,
        device_class,
    ):
        """Initialize the modbus register sensor."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else None
        self._register = int(register)
        self._bit_number = int(register)
        self._unit_of_measurement = unit_of_measurement
        self._count = count
        self._device_class = device_class
        self._value = None
        self._available = True

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if not state:
            return
        self._value = state.state == STATE_ON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def update(self):
        """Update the state of the sensor."""
        try:
            result = self._hub.read_holding_registers(
                self._slave, self._register, self._count
            )
        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        register_index = self._bit_number // 16
        register_bit_mask = 1 << (self._bit_number % 16)
        self._value = bool(result.registers[register_index] & register_bit_mask)
        self._available = True
