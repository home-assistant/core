"""Support for Modbus covers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import SUPPORT_CLOSE, SUPPORT_OPEN, CoverEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COVERS,
    CONF_NAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .base_platform import BasePlatform
from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_REGISTER,
    CONF_INPUT_TYPE,
    CONF_REGISTER,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Read configuration and create Modbus cover."""
    if discovery_info is None:
        _LOGGER.warning(
            "You're trying to init Modbus Cover in an unsupported way."
            " Check https://www.home-assistant.io/integrations/modbus/#configuring-platform-cover"
            " and fix your configuration"
        )
        return

    covers = []
    for cover in discovery_info[CONF_COVERS]:
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        covers.append(ModbusCover(hub, cover))

    async_add_entities(covers)


class ModbusCover(BasePlatform, CoverEntity, RestoreEntity):
    """Representation of a Modbus cover."""

    def __init__(
        self,
        hub: ModbusHub,
        config: dict[str, Any],
    ) -> None:
        """Initialize the modbus cover."""
        config[CONF_ADDRESS] = "0"
        config[CONF_INPUT_TYPE] = ""
        super().__init__(hub, config)
        self._coil = config.get(CALL_TYPE_COIL)
        self._register = config.get(CONF_REGISTER)
        self._state_closed = config[CONF_STATE_CLOSED]
        self._state_closing = config[CONF_STATE_CLOSING]
        self._state_open = config[CONF_STATE_OPEN]
        self._state_opening = config[CONF_STATE_OPENING]
        self._status_register = config.get(CONF_STATUS_REGISTER)
        self._status_register_type = config[CONF_STATUS_REGISTER_TYPE]

        # If we read cover status from coil, and not from optional status register,
        # we interpret boolean value False as closed cover, and value True as open cover.
        # Intermediate states are not supported in such a setup.
        if self._coil is not None:
            self._write_type = CALL_TYPE_WRITE_COIL
            if self._status_register is None:
                self._state_closed = False
                self._state_open = True
                self._state_closing = None
                self._state_opening = None

        # If we read cover status from the main register (i.e., an optional
        # status register is not specified), we need to make sure the register_type
        # is set to "holding".
        if self._register is not None:
            self._write_type = CALL_TYPE_WRITE_REGISTER
            if self._status_register is None:
                self._status_register = self._register
                self._status_register_type = CALL_TYPE_REGISTER_HOLDING

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            convert = {
                STATE_CLOSED: self._state_closed,
                STATE_CLOSING: self._state_closing,
                STATE_OPENING: self._state_opening,
                STATE_OPEN: self._state_open,
                STATE_UNAVAILABLE: None,
                STATE_UNKNOWN: None,
            }
            self._value = convert[state.state]

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

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

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        result = await self._hub.async_pymodbus_call(
            self._slave, self._register, self._state_open, self._write_type
        )
        self._available = result is not None
        await self.async_update()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        result = await self._hub.async_pymodbus_call(
            self._slave, self._register, self._state_closed, self._write_type
        )
        self._available = result is not None
        await self.async_update()

    async def async_update(self, now=None):
        """Update the state of the cover."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        if self._coil is not None and self._status_register is None:
            self._value = await self._async_read_coil()
        else:
            self._value = await self._async_read_status_register()

        self.async_write_ha_state()

    async def _async_read_status_register(self) -> int | None:
        """Read status register using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, self._status_register, 1, self._status_register_type
        )
        if result is None:
            self._available = False
            return None

        value = int(result.registers[0])
        self._available = True

        return value

    async def _async_read_coil(self) -> bool | None:
        """Read coil using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, self._coil, 1, CALL_TYPE_COIL
        )
        if result is None:
            self._available = False
            return None

        value = bool(result.bits[0] & 1)
        return value
