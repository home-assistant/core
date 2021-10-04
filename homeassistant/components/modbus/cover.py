"""Support for Modbus covers."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ENTITY_ID_FORMAT,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    CoverEntity,
)
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .base_platform import BasePlatform
from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_REGISTER,
    CONF_ADDRESS_CLOSE,
    CONF_MAX_SECONDS_TO_COMPLETE,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
    CONF_VERIFY,
)
from .modbus import ModbusHub

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus cover."""
    if discovery_info is None:  # pragma: no cover
        return

    covers = []
    for cover in discovery_info[CONF_COVERS]:
        hub: ModbusHub = get_hub(hass, discovery_info[CONF_NAME])
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
        super().__init__(hub, config)
        self.entity_id = ENTITY_ID_FORMAT.format(self._id)
        self._state_closed = config[CONF_STATE_CLOSED]
        self._state_closing = config[CONF_STATE_CLOSING]
        self._state_open = config[CONF_STATE_OPEN]
        self._state_opening = config[CONF_STATE_OPENING]
        self._status_register = config.get(CONF_STATUS_REGISTER)
        self._status_register_type = config[CONF_STATUS_REGISTER_TYPE]
        self._max_seconds_to_complete = config.get(CONF_MAX_SECONDS_TO_COMPLETE)
        self._complete_watcher: Callable[[], None] | None = None
        self._attr_current_cover_position = None
        self._track_position: bool = (
            self._status_register is None and self._max_seconds_to_complete is not None
        )
        self._track_position_delta = 0
        self._track_position_watcher: None | CALLBACK_TYPE = None

        self._attr_supported_features = SUPPORT_OPEN | SUPPORT_CLOSE
        self._attr_is_closed = False

        # If we read cover status from coil, and not from optional status register,
        # we interpret boolean value False as closed cover, and value True as open cover.
        # Intermediate states are not supported in such a setup.
        if self._input_type == CALL_TYPE_COIL:
            self._write_type = CALL_TYPE_WRITE_COIL
            self._write_address_open = self._address
            self._write_address_close = config.get(CONF_ADDRESS_CLOSE, self._address)
            if self._status_register is None:
                self._state_closed = False
                self._state_open = True
                if self._write_address_open != self._write_address_close:
                    # If we configured two coil addressed we can identity closing and opening state,
                    # but not final state closed or open as we might stop the closing or opening process
                    self._state_closing = -1
                    self._state_opening = -2

                    self._address_open = self._write_address_open
                    self._address_close = self._write_address_close
                else:
                    self._state_closing = None
                    self._state_opening = None
        else:
            # If we read cover status from the main register (i.e., an optional
            # status register is not specified), we need to make sure the register_type
            # is set to "holding".
            self._write_type = CALL_TYPE_WRITE_REGISTER
            self._write_address_open = self._address
            self._write_address_close = self._address
            self._address_open = self._address
            self._address_close = self._address

        if self._status_register:
            self._address_open = self._status_register
            self._address_close = self._status_register
            self._input_type = self._status_register_type
        elif CONF_VERIFY in config:
            self._address_open = config[CONF_VERIFY].get(CONF_ADDRESS)
            self._address_close = config[CONF_VERIFY].get(
                CONF_ADDRESS_CLOSE, config[CONF_VERIFY].get(CONF_ADDRESS)
            )

    def init_update_listeners(self):
        """Initialize update listeners."""
        # override default behaviour as we register based on the verify address
        if (
            self._slave is not None
            and self._input_type
            and self._scan_group is not None
        ):
            # Register max address of listeners to ensure we query both coils
            max_address = max(self._address_open, self._address_close)
            if max_address is not None:
                self._hub.register_update_listener(
                    self._scan_group,
                    self._slave,
                    self._input_type,
                    max_address,
                    self.update,
                )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if state := await self.async_get_last_state():
            if (
                self._track_position
                and state.attributes.get(ATTR_CURRENT_POSITION) is not None
                and str(state.attributes.get(ATTR_CURRENT_POSITION)).isnumeric()
            ):
                self._attr_current_cover_position = int(
                    str(state.attributes.get(ATTR_CURRENT_POSITION))
                )

            convert = {
                STATE_CLOSED: self._state_closed,
                STATE_CLOSING: self._state_closing,
                STATE_OPENING: self._state_opening,
                STATE_OPEN: self._state_open,
                STATE_UNAVAILABLE: None,
                STATE_UNKNOWN: None,
            }
            self._set_attr_state = convert[state.state]

    @property
    def supported_features(self):
        """Flag supported features."""
        flags = SUPPORT_OPEN | SUPPORT_CLOSE
        if (
            self._input_type == CALL_TYPE_COIL
            and self._write_address_open != self._write_address_close
        ):
            flags = flags | SUPPORT_STOP
        return flags

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._value == self._state_opening

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._value == self._state_closing

    def _set_attr_state(self, value: str | bool | int) -> None:
        """Convert received value to HA state."""
        self._attr_is_opening = value == self._state_opening
        self._attr_is_closing = value == self._state_closing
        self._attr_is_closed = value == self._state_closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        if (
            self._write_type == CALL_TYPE_WRITE_COIL
            and self._write_address_close != self._write_address_open
        ):
            # If we use two different coils to control up and down, we need to ensure not both coils
            # get On state at the same time, therefore we use value not stored in state object
            # Write inverted state to opposite coil
            await self._hub.async_pymodbus_call(
                self._slave, self._write_address_close, False, self._write_type
            )
            result = await self._hub.async_pymodbus_call(
                self._slave, self._write_address_open, True, self._write_type
            )
        else:
            result = await self._hub.async_pymodbus_call(
                self._slave,
                self._write_address_open,
                self._state_open,
                self._write_type,
            )
        if self._status_register is None and self._max_seconds_to_complete is not None:
            if self._complete_watcher is not None:
                self._complete_watcher()
            self._complete_watcher = async_call_later(
                self.hass,
                timedelta(seconds=self._max_seconds_to_complete),
                self.async_mark_as_opened,
            )
        if self._track_position and self._max_seconds_to_complete is not None:
            if self._track_position_watcher is not None:
                self._track_position_watcher()
            self._track_position_delta = 1
            self._track_position_watcher = async_track_time_interval(
                self.hass,
                self.async_track_position,
                timedelta(seconds=self._max_seconds_to_complete / 100),
            )

        self._attr_available = result is not None
        await self.async_update()

    async def async_track_position(self, *_):
        """Track cover position."""
        self._attr_current_cover_position = (
            self._attr_current_cover_position or 0
        ) + self._track_position_delta
        if self._attr_current_cover_position > 100:
            self._attr_current_cover_position = 100
            if self._track_position_watcher is not None:
                self._track_position_watcher()
            self._track_position_watcher = None
        if self._attr_current_cover_position < 0:
            self._attr_current_cover_position = 0
            if self._track_position_watcher is not None:
                self._track_position_watcher()
            self._track_position_watcher = None

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if (
            self._write_type == CALL_TYPE_WRITE_COIL
            and self._write_address_close != self._write_address_open
        ):
            # If we use two different coils to control up and down, we need to ensure not both coils
            # get On state at the same time, therefore we use value not stored in state object
            # Write inverted state to opposite coil
            await self._hub.async_pymodbus_call(
                self._slave, self._write_address_open, False, self._write_type
            )
            result = await self._hub.async_pymodbus_call(
                self._slave, self._write_address_close, True, self._write_type
            )
        else:
            result = await self._hub.async_pymodbus_call(
                self._slave,
                self._write_address_close,
                self._state_closed,
                self._write_type,
            )
        if self._status_register is None and self._max_seconds_to_complete is not None:
            if self._complete_watcher is not None:
                self._complete_watcher()
            self._complete_watcher = async_call_later(
                self.hass,
                timedelta(seconds=self._max_seconds_to_complete),
                self.async_mark_as_closed,
            )
        if self._track_position and self._max_seconds_to_complete is not None:
            if self._track_position_watcher is not None:
                self._track_position_watcher()
            self._track_position_delta = -1
            self._track_position_watcher = async_track_time_interval(
                self.hass,
                self.async_track_position,
                timedelta(seconds=self._max_seconds_to_complete / 100),
            )

        self._attr_available = result is not None
        await self.async_update()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        if (
            self._write_type == CALL_TYPE_WRITE_COIL
            and self._write_address_close != self._write_address_open
        ):
            # Stop is only possible if cover is configured with two coil addresses
            await self._hub.async_pymodbus_call(
                self._slave, self._write_address_open, False, self._write_type
            )
            result = await self._hub.async_pymodbus_call(
                self._slave, self._write_address_close, False, self._write_type
            )
            self._available = result is not None
        if self._complete_watcher is not None:
            self._complete_watcher()
            self._complete_watcher = None

        if self._track_position_watcher is not None:
            self._track_position_watcher()
            self._track_position_watcher = None

        self._attr_available = result is not None
        await self.async_update()

    async def async_mark_as_opened(self, now=None):
        """Mark opening as completed."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_call_later
        if self._track_position:
            self._attr_current_cover_position = 100
        if self._track_position_watcher is not None:
            self._track_position_watcher()
            self._track_position_watcher = None
        self.update_value(self._state_open)
        return await self.async_mark_as_opened_or_closed(True)

    async def async_mark_as_closed(self, now=None):
        """Mark closing as completed."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_call_later
        if self._track_position:
            self._attr_current_cover_position = 0
        if self._track_position_watcher is not None:
            self._track_position_watcher()
            self._track_position_watcher = None
        self.update_value(self._state_closed)
        return await self.async_mark_as_opened_or_closed(False)

    async def async_mark_as_opened_or_closed(self, opened):
        """Mark opening or closing of cover as completed."""
        _LOGGER.debug(
            "mark cover as opened or closed: slave=%s, input_type=%s, address=%s, state=%s",
            self._slave,
            self._input_type,
            self._address,
            opened,
        )
        if (
            self._write_type == CALL_TYPE_WRITE_COIL
            and self._write_address_close != self._write_address_open
        ):
            if opened:
                result = await self._hub.async_pymodbus_call(
                    self._slave, self._write_address_open, False, self._write_type
                )
            else:
                result = await self._hub.async_pymodbus_call(
                    self._slave, self._write_address_close, False, self._write_type
                )
        else:
            if opened:
                result = await self._hub.async_pymodbus_call(
                    self._slave,
                    self._write_address_open,
                    self._state_open,
                    self._write_type,
                )
            else:
                result = await self._hub.async_pymodbus_call(
                    self._slave,
                    self._write_address_close,
                    self._state_closed,
                    self._write_type,
                )
        self._available = result is not None
        await self.async_update()

    async def async_update(self, now=None):
        """Update the state of the cover."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        if self._call_active:
            return
        self._call_active = True
        start_address = min(self._address_open, self._address_close)
        end_address = max(self._address_open, self._address_close)
        result = await self._hub.async_pymodbus_call(
            self._slave, start_address, end_address - start_address, self._input_type
        )
        self._call_active = False
        self.update(result, self._slave, self._input_type, 0)

    async def update(self, result, slaveId, input_type, address):
        """Update the state of the cover."""
        if result is None:
            if self._lazy_errors:
                self._lazy_errors -= 1
                return
            self._lazy_errors = self._lazy_error_count
            self._attr_available = False
            self.async_write_ha_state()
            return
        self._lazy_errors = self._lazy_error_count
        self._attr_available = True
        if input_type == CALL_TYPE_COIL:
            if self._address_open != self._address_close:
                # Get min_address of open and close, address will be relative to this address
                start_address = max(self._address_open, self._address_close)
                opening = bool(
                    result.bits[address + (self._address_open - start_address)] & 1
                )
                closing = bool(
                    result.bits[address + (self._address_close - start_address)] & 1
                )
                _LOGGER.debug(
                    "update cover slave=%s, input_type=%s, address=%s, address_open=%s, address_close=%s -> result=%s, opening=%s, closing=%s",
                    slaveId,
                    input_type,
                    address,
                    (self._address_open - start_address),
                    (self._address_close - start_address),
                    result.bits,
                    opening,
                    closing,
                )
                if opening:
                    self.update_value(self._state_opening)
                elif closing:
                    self.update_value(self._state_closing)
                else:
                    # we assume either closed or open based on previous status
                    if self._value == self._state_opening:
                        self.update_value(self._state_open)
                    elif self._value == self._state_closing:
                        self.update_value(self._state_closed)
            else:
                _LOGGER.debug(
                    "update cover slave=%s, input_type=%s, address=%s -> result=%s",
                    slaveId,
                    input_type,
                    address,
                    result.bits,
                )
                self._set_attr_state(bool(result.bits[address] & 1))
        else:
            _LOGGER.debug(
                "update cover slave=%s, input_type=%s, address=%s -> result=%s",
                slaveId,
                input_type,
                address,
                result.registers,
            )
            self._set_attr_state(int(result.registers[address]))
        self.async_write_ha_state()      
