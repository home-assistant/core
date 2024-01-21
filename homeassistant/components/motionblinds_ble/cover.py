"""Cover entities for the MotionBlinds BLE integration."""
from __future__ import annotations

from asyncio import Event
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
import logging
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_register_callback,
)
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    ATTR_CONNECTION_TYPE,
    CONF_ADDRESS,
    CONF_BLIND_TYPE,
    CONF_MAC_CODE,
    DOMAIN,
    ENTITY_NAME,
    EXCEPTION_NOT_CALIBRATED,
    ICON_VERTICAL_BLIND,
    MANUFACTURER,
    MotionBlindType,
    MotionCalibrationType,
)
from .motionblinds_ble.const import (
    SETTING_CALIBRATION_DISCONNECT_TIME,
    MotionConnectionType,
    MotionRunningType,
    MotionSpeedLevel,
)
from .motionblinds_ble.device import MotionDevice, MotionPositionInfo

_LOGGER = logging.getLogger(__name__)


def generic_method_decorator(
    method: Callable[[GenericBlind], Callable], func: Callable
) -> Callable:
    """Decorate a method by running another method before it."""

    async def wrapper(self, *args, **kwargs):
        return await method(self)(func, *args, **kwargs)

    return wrapper


def run_command(func: Callable) -> Callable:
    """Decorate a method that moves the motor position."""
    return generic_method_decorator(lambda self: self.run_command_function, func)


def no_run_command(func: Callable) -> Callable:
    """Decorate a method that does not move the motor position."""
    return generic_method_decorator(lambda self: self.no_run_command_function, func)


@dataclass
class MotionCoverEntityDescription(CoverEntityDescription):
    """Entity description of a cover entity with default values."""

    key: str = field(default=CoverDeviceClass.BLIND.value, init=False)
    translation_key: str = field(default=CoverDeviceClass.BLIND.value, init=False)
    device_class: CoverDeviceClass = field(default=CoverDeviceClass.SHADE, init=True)


COVER_TYPES: dict[str, MotionCoverEntityDescription] = {
    MotionBlindType.ROLLER.value: MotionCoverEntityDescription(),
    MotionBlindType.HONEYCOMB.value: MotionCoverEntityDescription(),
    MotionBlindType.ROMAN.value: MotionCoverEntityDescription(),
    MotionBlindType.VENETIAN.value: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.BLIND
    ),
    MotionBlindType.VENETIAN_TILT_ONLY.value: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.BLIND
    ),
    MotionBlindType.DOUBLE_ROLLER.value: MotionCoverEntityDescription(),
    MotionBlindType.CURTAIN.value: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.CURTAIN
    ),
    MotionBlindType.VERTICAL.value: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.CURTAIN, icon=ICON_VERTICAL_BLIND
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up blind based on a config entry."""

    blind_type = BLIND_TO_ENTITY_TYPE[entry.data[CONF_BLIND_TYPE]]
    blind = blind_type(entry)

    hass.data[DOMAIN][entry.entry_id] = blind

    async_add_entities([blind])


class GenericBlind(CoverEntity):
    """Representation of a blind."""

    device_address: str
    device_rssi: int | None = None
    _device: MotionDevice
    _attr_connection_type: MotionConnectionType = MotionConnectionType.DISCONNECTED
    _running_type: MotionRunningType | None = None

    _use_status_position_update_ui: bool = False

    _battery_callback: Callable[[int | None], None] | None = None
    _speed_callback: Callable[[MotionSpeedLevel | None], None] | None = None
    _connection_callback: Callable[[MotionConnectionType | None], None] | None = None
    _signal_strength_callback: Callable[[int | None], None] | None = None

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the blind."""
        _LOGGER.info(
            f"({entry.data[CONF_MAC_CODE]}) Setting up {entry.data[CONF_BLIND_TYPE]} cover entity ({BLIND_TO_ENTITY_TYPE[entry.data[CONF_BLIND_TYPE]].__name__})"
        )
        super().__init__()
        self.entity_description = COVER_TYPES[entry.data[CONF_BLIND_TYPE]]
        self.config_entry: ConfigEntry = entry
        self.device_address: str = entry.data[CONF_ADDRESS]
        self._attr_name: str = ENTITY_NAME.format(mac_code=entry.data[CONF_MAC_CODE])
        self._attr_unique_id: str = entry.data[CONF_ADDRESS]
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_MAC_CODE])},
            manufacturer=MANUFACTURER,
            name=self._attr_name,
        )
        self._attr_is_closed: bool | None = None
        self._attr_is_opening: bool | None = None
        self._attr_is_closing: bool | None = None
        self._attr_should_poll: bool = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        ble_device = (
            async_ble_device_from_address(self.hass, self.device_address)
            if self.device_address
            else None
        )
        self._device = MotionDevice(
            self.device_address, ble_device, device_name=self._attr_name
        )
        async_register_callback(
            self.hass,
            self.async_update_ble_device,
            BluetoothCallbackMatcher(address=self.device_address),
            BluetoothScanningMode.ACTIVE,
        )
        # Pass functions used to schedule tasks
        self._device.set_ha_create_task(
            partial(
                self.config_entry.async_create_task,
                hass=self.hass,
                name=self.device_address,
            )
        )
        self._device.set_ha_call_later(partial(async_call_later, hass=self.hass))
        self.hass.data[DOMAIN][self.entity_id] = self
        # Register callbacks
        self._device.register_running_callback(self.async_update_running)
        self._device.register_position_callback(self.async_update_position)
        self._device.register_connection_callback(self.async_update_connection)
        self._device.register_status_callback(self.async_update_status)
        await super().async_added_to_hass()

    async def async_update(self) -> None:
        """Update state, called by HA if there is a poll interval and by the service homeassistant.update_entity."""
        _LOGGER.info(f"({self.config_entry.data[CONF_MAC_CODE]}) Updating entity")
        await self.async_connect()

    def async_refresh_disconnect_timer(
        self, timeout: int | None = None, force: bool = False
    ) -> None:
        """Refresh the time before the blind is disconnected."""
        self._device.refresh_disconnect_timer(timeout, force)

    async def async_connect(self, notification_delay: bool = False) -> bool:
        """Connect to the blind."""
        self._use_status_position_update_ui = True
        return await self._device.connect(notification_delay)

    async def async_disconnect(self, **kwargs: Any) -> None:
        """Disconnect the blind."""
        self._use_status_position_update_ui = False
        await self._device.disconnect()

    @no_run_command
    async def async_status_query(self, **kwargs: Any) -> None:
        """Send a status query to the blind."""
        self._use_status_position_update_ui = True
        if await self._device.status_query():
            self._use_status_position_update_ui = False

    @run_command
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop moving the blind."""
        _LOGGER.info(f"({self.config_entry.data[CONF_MAC_CODE]}) Stopping")
        await self._device.stop()

    @run_command
    async def async_favorite(self, **kwargs: Any) -> None:
        """Move the blind to the favorite position."""
        _LOGGER.info(
            f"({self.config_entry.data[CONF_MAC_CODE]}) Going to favorite position"
        )
        await self._device.favorite()
        self.async_update_running(MotionRunningType.UNKNOWN)

    @no_run_command
    async def async_speed(self, speed_level: MotionSpeedLevel, **kwargs: Any) -> None:
        """Change the speed level of the device."""
        _LOGGER.info(
            f"({self.config_entry.data[CONF_MAC_CODE]}) Changing speed to {speed_level.name.lower()}"
        )
        await self._device.speed(speed_level)

    def async_update_running(
        self, running_type: MotionRunningType | None, write_state: bool = True
    ) -> None:
        """Update whether the blind is running (opening/closing) or not."""
        self._running_type = running_type
        self._attr_is_opening = (
            False
            if running_type
            in [None, MotionRunningType.STILL, MotionRunningType.UNKNOWN]
            else running_type is MotionRunningType.OPENING
        )
        self._attr_is_closing = (
            False
            if running_type
            in [None, MotionRunningType.STILL, MotionRunningType.UNKNOWN]
            else running_type is not MotionRunningType.OPENING
        )
        if running_type is not MotionRunningType.STILL:
            self._attr_is_closed = None
        if write_state:
            self.async_write_ha_state()

    @callback
    def async_update_position(
        self,
        new_position_percentage: int,
        new_angle_percentage: int,
        end_position_info: MotionPositionInfo,
    ) -> None:
        """Update the position of the motor."""
        _LOGGER.debug(
            f"({self.config_entry.data[CONF_MAC_CODE]}) Received position update: {new_position_percentage}, tilt: {new_angle_percentage}"
        )
        if isinstance(self, PositionCalibrationBlind):
            self.async_update_calibration(end_position_info)
        # Only update running type to still if position has changed
        if self._attr_current_cover_position != 100 - new_position_percentage:
            self.async_update_running(MotionRunningType.STILL, write_state=False)
        self._attr_current_cover_position = 100 - new_position_percentage
        self._attr_current_cover_tilt_position = 100 - new_angle_percentage
        self._attr_is_closed = self._attr_current_cover_position == 0
        self.async_write_ha_state()

    @callback
    def async_update_connection(self, connection_type: MotionConnectionType) -> None:
        """Update the connection status."""
        _LOGGER.info(
            f"({self.config_entry.data[CONF_MAC_CODE]}) {connection_type.title()}"
        )
        self._attr_connection_type = connection_type
        if self._connection_callback is not None:
            self._connection_callback(connection_type)
        # Reset states if connection is lost, since we don't know the cover position anymore
        if connection_type is MotionConnectionType.DISCONNECTED:
            self._use_status_position_update_ui = False
            self.async_update_running(None, write_state=False)
            self._attr_current_cover_position = None
            self._attr_current_cover_tilt_position = None
            if self._speed_callback is not None:
                self._speed_callback(None)
            if self._battery_callback is not None:
                self._battery_callback(None)
        self.async_write_ha_state()

    @callback
    def async_update_status(
        self,
        position_percentage: int,
        tilt_percentage: int,
        battery_percentage: int,
        speed_level: MotionSpeedLevel | None,
        end_position_info: MotionPositionInfo,
    ) -> None:
        """Update motor status, e.g. position, tilt and battery percentage."""
        _LOGGER.debug(
            f"({self.config_entry.data[CONF_MAC_CODE]}) Received status update; position: {position_percentage}, tilt: {tilt_percentage}; battery: {battery_percentage}; speed: {speed_level.name if speed_level is not None else None}; top position set: {end_position_info.up}; bottom position set: {end_position_info.down}; favorite position set: {end_position_info.favorite}"
        )
        # Only update position based on feedback when necessary and end positions are set, otherwise cover UI will jump around
        if self._use_status_position_update_ui and end_position_info.up:
            self._attr_current_cover_position = 100 - position_percentage
            self._attr_current_cover_tilt_position = 100 - tilt_percentage
            self._attr_is_closed = self._attr_current_cover_position == 0

        self._use_status_position_update_ui = False

        if self._battery_callback is not None:
            self._battery_callback(battery_percentage)
        if self._speed_callback is not None:
            self._speed_callback(speed_level)
        if isinstance(self, PositionCalibrationBlind):
            self.async_update_calibration(end_position_info)
        self.async_write_ha_state()

    @callback
    def async_update_ble_device(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Update the BLEDevice."""
        _LOGGER.info(f"({service_info.address}) New BLE device found")
        self._device.set_ble_device(service_info.device)
        self.device_rssi = service_info.advertisement.rssi
        if callable(self._signal_strength_callback):
            self._signal_strength_callback(self.device_rssi)

    def async_register_battery_callback(
        self, _battery_callback: Callable[[int | None], None]
    ) -> None:
        """Register the callback used to update the battery percentage."""
        self._battery_callback = _battery_callback

    def async_register_speed_callback(
        self, _speed_callback: Callable[[MotionSpeedLevel | None], None]
    ) -> None:
        """Register the callback used to update the speed level."""
        self._speed_callback = _speed_callback

    def async_register_connection_callback(
        self, _connection_callback: Callable[[MotionConnectionType | None], None]
    ) -> None:
        """Register the callback used to update the connection."""
        self._connection_callback = _connection_callback

    def async_register_signal_strength_callback(
        self, _signal_strength_callback: Callable[[int | None], None]
    ) -> None:
        """Register the callback used to update the signal strength."""
        self._signal_strength_callback = _signal_strength_callback

    @property
    def extra_state_attributes(self) -> Mapping[str, str]:
        """Return the state attributes."""
        return {ATTR_CONNECTION_TYPE: self._attr_connection_type}

    async def before_command_function(self, *args, **kwargs) -> None:
        """Run some code before executing any command."""
        if self._attr_connection_type is MotionConnectionType.CONNECTED:
            self.async_refresh_disconnect_timer()

    # Decorator
    async def run_command_function(
        self,
        func: Callable,
        ignore_end_positions_not_set: bool = False,
        *args,
        **kwargs,
    ) -> bool:
        """Run some code before executing any command that moves the position of the blind."""
        await self.before_command_function(*args, **kwargs)
        if self._attr_connection_type is not MotionConnectionType.CONNECTED:
            self._use_status_position_update_ui = False
        return await func(
            self,
            *args,
            ignore_end_positions_not_set=ignore_end_positions_not_set,
            **kwargs,
        )

    # Decorator
    async def no_run_command_function(self, func: Callable, *args, **kwargs) -> bool:
        """Run some code before executing any command that does not move the position of the blind."""
        await self.before_command_function(*args, **kwargs)
        if self._attr_connection_type is not MotionConnectionType.CONNECTED:
            self._use_status_position_update_ui = True
            self.async_update_running(MotionRunningType.STILL)
        return await func(self, *args, **kwargs)


class PositionBlind(GenericBlind):
    """Representation of a blind with position capability."""

    _attr_supported_features: CoverEntityFeature | None = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    @run_command
    async def async_open_cover(
        self, ignore_end_positions_not_set: bool = False, **kwargs: Any
    ) -> None:
        """Open the blind."""
        _LOGGER.info(f"({self.config_entry.data[CONF_MAC_CODE]}) Opening")
        self.async_update_running(MotionRunningType.OPENING)
        if await self._device.open(
            ignore_end_positions_not_set=ignore_end_positions_not_set
        ):
            self.async_write_ha_state()
        else:
            self.async_update_running(MotionRunningType.STILL)

    @run_command
    async def async_close_cover(
        self, ignore_end_positions_not_set: bool = False, **kwargs: Any
    ) -> None:
        """Close the blind."""
        _LOGGER.info(f"({self.config_entry.data[CONF_MAC_CODE]}) Closing")
        self.async_update_running(MotionRunningType.CLOSING)
        if await self._device.close(
            ignore_end_positions_not_set=ignore_end_positions_not_set
        ):
            self.async_write_ha_state()
        else:
            self.async_update_running(MotionRunningType.STILL)

    @run_command
    async def async_set_cover_position(
        self, ignore_end_positions_not_set: bool = False, **kwargs: Any
    ) -> None:
        """Move the blind to a specific position."""
        new_position: int | None = (
            100 - int(kwargs[ATTR_POSITION])
            if ATTR_POSITION in kwargs and kwargs[ATTR_POSITION] is not None
            else None
        )

        _LOGGER.info(
            f"({self.config_entry.data[CONF_MAC_CODE]}) Setting position to {new_position}"
        )
        self.async_update_running(
            MotionRunningType.UNKNOWN
            if self._attr_current_cover_position is None or new_position is None
            else MotionRunningType.STILL
            if new_position == 100 - self._attr_current_cover_position
            else MotionRunningType.OPENING
            if new_position < 100 - self._attr_current_cover_position
            else MotionRunningType.CLOSING
        )
        if await self._device.percentage(
            new_position, ignore_end_positions_not_set=ignore_end_positions_not_set
        ):
            self.async_write_ha_state()
        else:
            self.async_update_running(MotionRunningType.STILL)


class TiltBlind(GenericBlind):
    """Representation of a blind with tilt capability."""

    _attr_supported_features: CoverEntityFeature | None = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    @run_command
    async def async_open_cover_tilt(
        self, ignore_end_positions_not_set: bool = False, **kwargs: Any
    ) -> None:
        """Tilt the blind open."""
        _LOGGER.info(f"({self.config_entry.data[CONF_MAC_CODE]}) Tilt opening")
        self.async_update_running(MotionRunningType.OPENING)
        if await self._device.open_tilt(
            ignore_end_positions_not_set=ignore_end_positions_not_set
        ):
            self.async_write_ha_state()
        else:
            self.async_update_running(MotionRunningType.STILL)

    @run_command
    async def async_close_cover_tilt(
        self, ignore_end_positions_not_set: bool = False, **kwargs: Any
    ) -> None:
        """Tilt the blind closed."""
        _LOGGER.info(f"({self.config_entry.data[CONF_MAC_CODE]}) Tilt closing")
        self.async_update_running(MotionRunningType.CLOSING)
        if await self._device.close_tilt(
            ignore_end_positions_not_set=ignore_end_positions_not_set
        ):
            self.async_write_ha_state()
        else:
            self.async_update_running(MotionRunningType.STILL)

    @run_command
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop tilting the blind."""
        await self.async_stop_cover(**kwargs)

    @run_command
    async def async_set_cover_tilt_position(
        self, ignore_end_positions_not_set: bool = False, **kwargs: Any
    ) -> None:
        """Tilt the blind to a specific position."""
        new_tilt_position: int | None = (
            100 - int(kwargs[ATTR_TILT_POSITION])
            if ATTR_TILT_POSITION in kwargs and kwargs[ATTR_TILT_POSITION] is not None
            else None
        )

        _LOGGER.info(
            f"({self.config_entry.data[CONF_MAC_CODE]}) Setting tilt position to {new_tilt_position}"
        )
        self.async_update_running(
            MotionRunningType.STILL
            if self._attr_current_cover_tilt_position is None
            or new_tilt_position is None
            or new_tilt_position == 100 - self._attr_current_cover_tilt_position
            else MotionRunningType.OPENING
            if new_tilt_position < 100 - self._attr_current_cover_tilt_position
            else MotionRunningType.CLOSING
        )
        if await self._device.percentage_tilt(
            new_tilt_position, ignore_end_positions_not_set=ignore_end_positions_not_set
        ):
            self.async_write_ha_state()
        else:
            self.async_update_running(MotionRunningType.STILL)


class PositionTiltBlind(PositionBlind, TiltBlind):
    """Representation of a blind with position & tilt capabilities."""

    _attr_supported_features: CoverEntityFeature | None = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )


class PositionCalibrationBlind(PositionBlind):
    """Representation of a blind with position & calibration capabilities."""

    _calibration_type: MotionCalibrationType | None = None
    _calibration_callback: Callable[[MotionCalibrationType | None], None] | None = None

    def async_update_running(
        self, running_type: MotionRunningType | None, write_state: bool = True
    ) -> None:
        """Update the running status."""
        if (
            self._calibration_type is MotionCalibrationType.UNCALIBRATED
            and running_type
            in [
                MotionRunningType.OPENING,
                MotionRunningType.CLOSING,
                MotionRunningType.UNKNOWN,
            ]
        ):
            # Curtain motor will calibrate if not calibrated and moved to some position
            _LOGGER.info(
                f"({self.config_entry.data[CONF_MAC_CODE]}) Calibration status: calibrating"
            )
            self._calibration_type = MotionCalibrationType.CALIBRATING
            if callable(self._calibration_callback):
                self._calibration_callback(MotionCalibrationType.CALIBRATING)
            self.async_refresh_disconnect_timer(SETTING_CALIBRATION_DISCONNECT_TIME)
        super().async_update_running(running_type, write_state)

    @callback
    def async_update_calibration(self, end_position_info: MotionPositionInfo) -> None:
        """Update the calibration status."""
        new_calibration_type = (
            MotionCalibrationType.CALIBRATED  # Calibrated if end positions are set
            if end_position_info.up
            else MotionCalibrationType.CALIBRATING  # Calibrating if no end positions, and motor is running
            if self._running_type is not None
            and self._running_type
            in [MotionRunningType.OPENING, MotionRunningType.CLOSING]
            else MotionCalibrationType.UNCALIBRATED
        )
        _LOGGER.info(
            f"({self.config_entry.data[CONF_MAC_CODE]}) Calibration status: {new_calibration_type}"
        )

        if (
            self._calibration_type is MotionCalibrationType.CALIBRATING
            and new_calibration_type is not MotionCalibrationType.CALIBRATING
        ):
            # Refresh disconnect timeout to default value if finished calibrating
            self.async_refresh_disconnect_timer(force=True)
        self._calibration_type = new_calibration_type
        if callable(self._calibration_callback):
            self._calibration_callback(new_calibration_type)

    def async_register_calibration_callback(
        self, _calibration_callback: Callable[[MotionCalibrationType | None], None]
    ) -> None:
        """Register the callback used to update the calibration."""
        self._calibration_callback = _calibration_callback

    @callback
    def async_update_connection(self, connection_type: MotionConnectionType) -> None:
        """Update the connection status."""
        if (
            self._calibration_callback is not None
            and connection_type is MotionConnectionType.DISCONNECTED
        ):
            # Set calibration to None if disconnected
            self._calibration_callback(None)
            self._running_type = None
        super().async_update_connection(connection_type)

    async def async_connect(self, notification_delay: bool = True) -> bool:
        """Connect to the blind, add a delay before sending the status query."""
        return await super().async_connect(notification_delay=notification_delay)

    # Decorator
    async def run_command_function(self, func: Callable, *args, **kwargs) -> bool:
        """Run before every command that moves a blind, return whether or not to proceed with the command."""
        return await super().run_command_function(func, True, *args, **kwargs)


class PositionTiltCalibrationBlind(PositionCalibrationBlind, PositionTiltBlind):
    """Representation of a blind with position, tilt and calibration capabilities."""

    _calibration_event: Event = Event()

    # Decorator
    async def run_command_function(self, func: Callable, *args, **kwargs) -> bool:
        """Run before every command that moves a blind, return whether or not to proceed with the command."""
        # Do not throw an exception if the end positions are not set but a move command is given
        if not self._device.is_connected():
            self._calibration_event.clear()
            if not await self.async_connect():
                return False
            # Wait for calibration attribute to get a value
            await self._calibration_event.wait()
        # If motor is not calibrated, raise an exception
        if self._calibration_type is not MotionCalibrationType.CALIBRATED:
            raise NotCalibratedException(
                EXCEPTION_NOT_CALIBRATED.format(device_name=self._attr_name)
            )
        return await super().run_command_function(func, *args, **kwargs)

    @callback
    def async_update_calibration(self, end_position_info: MotionPositionInfo) -> None:
        """Update the calibration status."""
        super().async_update_calibration(end_position_info)
        self._calibration_event.set()


class NotCalibratedException(Exception):
    """Exception to indicate the blinds are not calibrated."""


BLIND_TO_ENTITY_TYPE: dict[str, type[GenericBlind]] = {
    MotionBlindType.ROLLER.value: PositionBlind,
    MotionBlindType.HONEYCOMB.value: PositionBlind,
    MotionBlindType.ROMAN.value: PositionBlind,
    MotionBlindType.VENETIAN.value: PositionTiltBlind,
    MotionBlindType.VENETIAN_TILT_ONLY.value: TiltBlind,
    MotionBlindType.DOUBLE_ROLLER.value: PositionTiltBlind,
    MotionBlindType.CURTAIN.value: PositionCalibrationBlind,
    MotionBlindType.VERTICAL.value: PositionTiltCalibrationBlind,
}
