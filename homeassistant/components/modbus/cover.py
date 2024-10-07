"""Support for Modbus covers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.const import (
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_REGISTER,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
)
from .entity import BasePlatform
from .modbus import ModbusHub

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus cover."""
    if discovery_info is None:
        return

    covers = []
    for cover in discovery_info[CONF_COVERS]:
        hub: ModbusHub = get_hub(hass, discovery_info[CONF_NAME])
        covers.append(ModbusCover(hass, hub, cover))

    async_add_entities(covers)


class ModbusCover(BasePlatform, CoverEntity, RestoreEntity):
    """Representation of a Modbus cover."""

    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        hass: HomeAssistant,
        hub: ModbusHub,
        config: dict[str, Any],
    ) -> None:
        """Initialize the modbus cover."""
        super().__init__(hass, hub, config)
        self._state_closed = config[CONF_STATE_CLOSED]
        self._state_closing = config[CONF_STATE_CLOSING]
        self._state_open = config[CONF_STATE_OPEN]
        self._state_opening = config[CONF_STATE_OPENING]
        self._status_register = config.get(CONF_STATUS_REGISTER)
        self._status_register_type = config[CONF_STATUS_REGISTER_TYPE]

        self._attr_is_closed = False

        # If we read cover status from coil, and not from optional status register,
        # we interpret boolean value False as closed cover, and value True as open cover.
        # Intermediate states are not supported in such a setup.
        if self._input_type == CALL_TYPE_COIL:
            self._write_type = CALL_TYPE_WRITE_COIL
            self._write_address = self._address
            if self._status_register is None:
                self._state_closed = False
                self._state_open = True
                self._state_closing = None
                self._state_opening = None
        else:
            # If we read cover status from the main register (i.e., an optional
            # status register is not specified), we need to make sure the register_type
            # is set to "holding".
            self._write_type = CALL_TYPE_WRITE_REGISTER
            self._write_address = self._address
        if self._status_register:
            self._address = self._status_register
            self._input_type = self._status_register_type

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if state := await self.async_get_last_state():
            convert = {
                STATE_CLOSED: self._state_closed,
                STATE_CLOSING: self._state_closing,
                STATE_OPENING: self._state_opening,
                STATE_OPEN: self._state_open,
                STATE_UNAVAILABLE: None,
                STATE_UNKNOWN: None,
            }
            self._set_attr_state(convert[state.state])

    def _set_attr_state(self, value: str | bool | int) -> None:
        """Convert received value to HA state."""
        self._attr_is_opening = value == self._state_opening
        self._attr_is_closing = value == self._state_closing
        self._attr_is_closed = value == self._state_closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        result = await self._hub.async_pb_call(
            self._slave, self._write_address, self._state_open, self._write_type
        )
        self._attr_available = result is not None
        await self.async_update()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        result = await self._hub.async_pb_call(
            self._slave, self._write_address, self._state_closed, self._write_type
        )
        self._attr_available = result is not None
        await self.async_update()

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the state of the cover."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        result = await self._hub.async_pb_call(
            self._slave, self._address, 1, self._input_type
        )
        if result is None:
            self._attr_available = False
            self.async_write_ha_state()
            return
        self._attr_available = True
        if self._input_type == CALL_TYPE_COIL:
            self._set_attr_state(bool(result.bits[0] & 1))
        else:
            self._set_attr_state(int(result.registers[0]))
        self.async_write_ha_state()
