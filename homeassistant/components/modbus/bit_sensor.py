"""Support for Modbus Bit sensors."""
from __future__ import annotations

from datetime import timedelta
from functools import lru_cache, partial
import logging
import time

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    STATE_ON,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import DiscoveryInfoType, HomeAssistantType

from .const import (
    CALL_TYPE_REGISTER_INPUT,
    CONF_BIT_NUMBER,
    CONF_BIT_SENSORS,
    CONF_INPUT_TYPE,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def _read_cached(hub, method, ttl_bucket, *args, **kvargs):
    """Return cached or invoke the Hub read_* method."""
    return getattr(hub, method)(*args, **kvargs)


class ModbusReadCache:
    """Wraps Modbus Hub and provide cached methods."""

    CACHED_METHODS = ["read_input_registers", "read_holding_registers"]
    CACHE_RESET_METHODS = "write_"

    def __init__(self, hub):
        """Init the read cache."""
        self._hub = hub

    def __getattr__(self, attr):
        """Forward calls to the Hub object or use cached."""
        if attr.startswith(ModbusReadCache.CACHE_RESET_METHODS):
            _read_cached.cache_clear()
        if attr not in ModbusReadCache.CACHED_METHODS:
            return getattr(self._hub, attr)

        return partial(_read_cached, self._hub, attr, int(time.time()))


def setup_bit_sensors(
    hass: HomeAssistantType,
    discovery_info: DiscoveryInfoType | None = None,
) -> [BinarySensorEntity]:
    """Set up the Modbus Bit sensors."""
    sensors = []

    if discovery_info is None:
        return sensors

    for entry in discovery_info.get(CONF_BIT_SENSORS, []):
        words_count = int(entry[CONF_COUNT])
        bit_number = int(entry[CONF_BIT_NUMBER])

        if bit_number >= words_count * 16:
            _LOGGER.error(
                "Bit number for the %s sensor is out of range",
                entry[CONF_NAME],
            )
            continue

        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        sensors.append(
            ModbusBitSensor(
                hub,
                entry[CONF_NAME],
                entry.get(CONF_SLAVE),
                entry[CONF_ADDRESS],
                entry[CONF_INPUT_TYPE],
                bit_number,
                words_count,
                entry.get(CONF_DEVICE_CLASS),
                entry[CONF_SCAN_INTERVAL],
            )
        )

    return sensors


class ModbusBitSensorBase(RestoreEntity, BinarySensorEntity):
    """Base class for the Modbus sensor."""

    def __init__(
        self,
        hub,
        name,
        slave,
        register,
        register_type,
        count,
        device_class,
        scan_interval,
    ):
        """Initialize the modbus sensor."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else None
        self._register = int(register)
        self._count = count
        self._device_class = device_class
        self._register_type = register_type
        self._value = None
        self._available = True
        self._scan_interval = timedelta(seconds=scan_interval)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """

        # Handle polling directly in this entity
        return False

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available


class ModbusBitSensor(ModbusBitSensorBase):
    """Modbus bit sensor."""

    def __init__(
        self,
        hub,
        name,
        slave,
        register,
        register_type,
        bit_number,
        count,
        device_class,
        scan_interval,
    ):
        """Initialize the modbus bit sensor."""
        super().__init__(
            ModbusReadCache(hub),
            name,
            slave,
            register,
            register_type,
            count,
            device_class,
            scan_interval,
        )
        self._bit_number = int(bit_number)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if state:
            self._value = state.state == STATE_ON

        async_track_time_interval(
            self.hass, lambda arg: self._update(), self._scan_interval
        )

    def _update(self):
        """Update the state of the sensor."""
        try:
            if self._register_type == CALL_TYPE_REGISTER_INPUT:
                result = self._hub.read_input_registers(
                    self._slave, self._register, self._count
                )
            else:
                result = self._hub.read_holding_registers(
                    self._slave, self._register, self._count
                )

        except ConnectionException:
            self._available = False
            self.schedule_update_ha_state()
            return
        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            self.schedule_update_ha_state()
            return

        register_index = self._bit_number // 16
        register_bit_mask = 1 << (self._bit_number % 16)
        self._value = bool(result.registers[register_index] & register_bit_mask)
        self._available = True
        self.schedule_update_ha_state()
