"""Support for Modbus covers."""
from datetime import timedelta
from typing import Any, Dict, Optional

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.components.cover import SUPPORT_CLOSE, SUPPORT_OPEN, CoverEntity
from homeassistant.const import (
    CONF_COVERS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

from . import ModbusHub
from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_REGISTER,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
    MODBUS_DOMAIN,
)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities,
    discovery_info: Optional[DiscoveryInfoType] = None,
):
    """Read configuration and create Modbus cover."""
    if discovery_info is None:
        return

    covers = []
    for cover in discovery_info[CONF_COVERS]:
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        covers.append(ModbusCover(hub, cover))

    async_add_entities(covers)


class ModbusCover(CoverEntity, RestoreEntity):
    """Representation of a Modbus cover."""

    def __init__(
        self,
        hub: ModbusHub,
        config: Dict[str, Any],
    ):
        """Initialize the modbus cover."""
        self._hub: ModbusHub = hub
        self._coil = config.get(CALL_TYPE_COIL)
        self._device_class = config.get(CONF_DEVICE_CLASS)
        self._name = config[CONF_NAME]
        self._register = config.get(CONF_REGISTER)
        self._slave = config[CONF_SLAVE]
        self._state_closed = config[CONF_STATE_CLOSED]
        self._state_closing = config[CONF_STATE_CLOSING]
        self._state_open = config[CONF_STATE_OPEN]
        self._state_opening = config[CONF_STATE_OPENING]
        self._status_register = config.get(CONF_STATUS_REGISTER)
        self._status_register_type = config[CONF_STATUS_REGISTER_TYPE]
        self._scan_interval = timedelta(seconds=config[CONF_SCAN_INTERVAL])
        self._value = None
        self._available = True

        # If we read cover status from coil, and not from optional status register,
        # we interpret boolean value False as closed cover, and value True as open cover.
        # Intermediate states are not supported in such a setup.
        if self._coil is not None and self._status_register is None:
            self._state_closed = False
            self._state_open = True
            self._state_closing = None
            self._state_opening = None

        # If we read cover status from the main register (i.e., an optional
        # status register is not specified), we need to make sure the register_type
        # is set to "holding".
        if self._register is not None and self._status_register is None:
            self._status_register = self._register
            self._status_register_type = CALL_TYPE_REGISTER_HOLDING

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if not state:
            return
        self._value = state.state

        async_track_time_interval(
            self.hass, lambda arg: self._update(), self._scan_interval
        )

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._value == self._state_opening

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._value == self._state_closing

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._value == self._state_closed

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        # Handle polling directly in this entity
        return False

    def open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        if self._coil is not None:
            self._write_coil(True)
        else:
            self._write_register(self._state_open)

        self._update()

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if self._coil is not None:
            self._write_coil(False)
        else:
            self._write_register(self._state_closed)

        self._update()

    def _update(self):
        """Update the state of the cover."""
        if self._coil is not None and self._status_register is None:
            self._value = self._read_coil()
        else:
            self._value = self._read_status_register()

        self.schedule_update_ha_state()

    def _read_status_register(self) -> Optional[int]:
        """Read status register using the Modbus hub slave."""
        try:
            if self._status_register_type == CALL_TYPE_REGISTER_INPUT:
                result = self._hub.read_input_registers(
                    self._slave, self._status_register, 1
                )
            else:
                result = self._hub.read_holding_registers(
                    self._slave, self._status_register, 1
                )
        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        value = int(result.registers[0])
        self._available = True

        return value

    def _write_register(self, value):
        """Write holding register using the Modbus hub slave."""
        try:
            self._hub.write_register(self._slave, self._register, value)
        except ConnectionException:
            self._available = False
            return

        self._available = True

    def _read_coil(self) -> Optional[bool]:
        """Read coil using the Modbus hub slave."""
        try:
            result = self._hub.read_coils(self._slave, self._coil, 1)
        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        value = bool(result.bits[0] & 1)
        self._available = True

        return value

    def _write_coil(self, value):
        """Write coil using the Modbus hub slave."""
        try:
            self._hub.write_coil(self._slave, self._coil, value)
        except ConnectionException:
            self._available = False
            return

        self._available = True
