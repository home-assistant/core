"""Interfaces with Vaillant binary sensors."""

from abc import ABC
import logging

from pymultimatic.model import (
    BoilerStatus,
    Circulation,
    Device,
    Error,
    HolidayMode,
    OperatingModes,
    QuickMode,
    QuickModes,
    Room,
    SettingModes,
    SystemInfo,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_WINDOW,
    DOMAIN,
    BinarySensorEntity,
)
from homeassistant.util import Throttle

from . import ApiHub
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN as VAILLANT
from .entities import (
    VaillantBoilerEntity,
    VaillantBoxEntity,
    VaillantEntity,
    VaillantRoomEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Vaillant binary sensor platform."""
    sensors = []
    hub: ApiHub = hass.data[VAILLANT].api
    if hub.system:
        if hub.system.dhw and hub.system.dhw.circulation:
            sensors.append(CirculationSensor(hub.system.dhw.circulation))

        if hub.system.boiler_status:
            sensors.append(BoilerError(hub.system.boiler_status))

        if hub.system.info:
            sensors.append(BoxOnline(hub.system.info))
            sensors.append(BoxUpdate(hub.system.info))

        for room in hub.system.rooms:
            sensors.append(RoomWindow(room))
            for device in room.devices:
                if device.device_type == "VALVE":
                    sensors.append(RoomDeviceChildLock(device, room))

                sensors.append(RoomDeviceBattery(device, room))
                sensors.append(RoomDeviceConnectivity(device, room))

        entity = HolidayModeSensor(hub.system.holiday)
        sensors.append(entity)

        entity = QuickModeSensor(hub.system.quick_mode)
        sensors.append(entity)

        handler = VaillantSystemErrorHandler(
            hub, hass, async_add_entities, DEFAULT_SCAN_INTERVAL
        )
        await handler.update()

    _LOGGER.info("Adding %s binary sensor entities", len(sensors))

    async_add_entities(sensors, True)
    return True


class CirculationSensor(VaillantEntity, BinarySensorEntity):
    """Binary sensor for circulation running on or not."""

    def __init__(self, circulation: Circulation):
        """Initialize entity."""
        super().__init__(
            DOMAIN, DEVICE_CLASS_POWER, circulation.id, circulation.name, False
        )
        self._circulation = circulation
        self._active_mode = None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""

        return (
            self._active_mode.current == OperatingModes.ON
            or self._active_mode.sub == SettingModes.ON
            or self._active_mode.current == QuickModes.HOTWATER_BOOST
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return self._circulation is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._circulation = self.hub.system.dhw.circulation
        self._active_mode = self.hub.system.get_active_mode_circulation()


class RoomWindow(VaillantEntity, BinarySensorEntity):
    """Vaillant window binary sensor."""

    def __init__(self, room: Room):
        """Initialize entity."""
        super().__init__(DOMAIN, DEVICE_CLASS_WINDOW, room.name, room.name)
        self._room = room

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._room.window_open

    @property
    def available(self):
        """Return True if entity is available."""
        return self._room is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        new_room: Room = self.hub.find_component(self._room)

        if new_room:
            _LOGGER.debug(
                "New / old state: %s / %s", new_room.child_lock, self._room.child_lock
            )
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room


class RoomDevice(VaillantEntity, VaillantRoomEntity, BinarySensorEntity, ABC):
    """Base class for device in room."""

    def __init__(self, device: Device, room: Room, device_class):
        """Initialize entity."""
        VaillantEntity.__init__(self, DOMAIN, device_class, device.sgtin, device.name)
        VaillantRoomEntity.__init__(self, device)
        self._room = room
        self._device_class = device_class

    # pylint: disable=no-self-use
    def _find_device(self, new_room: Room, sgtin: str):
        """Find a device in a room."""
        if new_room:
            for device in new_room.devices:
                if device.sgtin == sgtin:
                    return device

    @property
    def available(self):
        """Return True if entity is available."""
        return self.device is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        new_room: Room = self.hub.find_component(self._room)
        new_device: Device = self._find_device(new_room, self.device.sgtin)

        if new_room:
            if new_device:
                _LOGGER.debug(
                    "New / old state: %s / %s",
                    new_device.battery_low,
                    self.device.battery_low,
                )
            else:
                _LOGGER.debug("Device %s doesn't exist anymore", self.device.sgtin)
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room
        self.device = new_device


class RoomDeviceChildLock(RoomDevice, BinarySensorEntity):
    """Binary sensor for valve child lock.

    At vaillant API, the lock is set at a room level, but it applies to all
    device inside the room.
    """

    def __init__(self, device: Device, room: Room):
        """Initialize entity."""
        super().__init__(device, room, DEVICE_CLASS_LOCK)

    @property
    def available(self):
        """Return True if entity is available."""
        return self._room is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        new_room: Room = self.hub.find_component(self._room)

        if new_room:
            _LOGGER.debug(
                "New / old state: %s / %s", new_room.child_lock, self._room.child_lock
            )
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room
        self.device = self._find_device(new_room, self.device.sgtin)

    @property
    def is_on(self):
        """According to the doc, true means unlock, false lock."""
        return not self._room.child_lock


class RoomDeviceBattery(RoomDevice):
    """Represent a device battery."""

    def __init__(self, device: Device, room: Room):
        """Initialize entity."""
        super().__init__(device, room, DEVICE_CLASS_BATTERY)

    @property
    def is_on(self):
        """According to the doc, true means normal, false low."""
        return self.device.battery_low


class RoomDeviceConnectivity(RoomDevice):
    """Device in room is out of reach or not."""

    def __init__(self, device: Device, room: Room):
        """Initialize entity."""
        super().__init__(device, room, DEVICE_CLASS_CONNECTIVITY)

    @property
    def is_on(self):
        """According to the doc, true means connected, false disconnected."""
        return not self.device.radio_out_of_reach


class BaseVaillantSystem(VaillantEntity, VaillantBoxEntity, BinarySensorEntity):
    """Base class for system wide binary sensor."""

    def __init__(self, info: SystemInfo, device_class, name, comp_id):
        """Initialize entity."""
        VaillantEntity.__init__(self, DOMAIN, device_class, name, comp_id, False)
        VaillantBoxEntity.__init__(self, info)

    @property
    def available(self):
        """Return True if entity is available."""
        return self.system_info is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        system_info: SystemInfo = self.hub.system.info

        if system_info:
            _LOGGER.debug(
                "Found new system status " "online? %s, up to date? %s",
                system_info.is_online,
                system_info.is_up_to_date,
            )
        else:
            _LOGGER.debug("System status doesn't exist anymore")
        self.system_info = system_info


class BoxUpdate(BaseVaillantSystem):
    """Update binary sensor."""

    def __init__(self, info: SystemInfo):
        """Init."""
        super().__init__(info, DEVICE_CLASS_POWER, "System update", "system_update")

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return not self.system_info.is_up_to_date


class BoxOnline(BaseVaillantSystem):
    """Check if box is online."""

    def __init__(self, info: SystemInfo):
        """Init."""
        BaseVaillantSystem.__init__(
            self, info, DEVICE_CLASS_CONNECTIVITY, "System Online", "system_online",
        )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.system_info.is_online


class BoilerError(VaillantEntity, BinarySensorEntity, VaillantBoilerEntity):
    """Check if there is some error."""

    def __init__(self, boiler_status: BoilerStatus):
        """Initialize entity."""
        VaillantEntity.__init__(
            self,
            DOMAIN,
            DEVICE_CLASS_PROBLEM,
            boiler_status.device_name,
            boiler_status.device_name,
            False,
        )
        VaillantBoilerEntity.__init__(self, boiler_status)
        self._state_attrs = {}

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.boiler_status is not None and self.boiler_status.is_error

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.boiler_status is not None:
            self._state_attrs = {
                "status_code": self.boiler_status.status_code,
                "title": self.boiler_status.title,
                "timestamp": self.boiler_status.timestamp,
            }
        return self._state_attrs

    async def vaillant_update(self):
        """Update specific for vaillant."""
        _LOGGER.debug("new boiler status is %s", self.hub.system.boiler_status)
        self.boiler_status = self.hub.system.boiler_status


class VaillantSystemErrorHandler:
    """Handler responsible for creating dynamically error binary sensor."""

    def __init__(self, hub, hass, async_add_entities, scan_interval) -> None:
        """Init."""
        self.hub = hub
        self._hass = hass
        self._async_add_entities = async_add_entities
        self.update = Throttle(scan_interval)(self._update)

    async def _update(self):
        if self.hub.system.errors:
            reg = await self._hass.helpers.entity_registry.async_get_registry()

            sensors = []
            for error in self.hub.system.errors:
                binary_sensor = VaillantSystemError(error)
                if not reg.async_is_registered(binary_sensor.entity_id):
                    sensors.append(binary_sensor)

            if sensors:
                self._async_add_entities(sensors)


class VaillantSystemError(VaillantEntity, BinarySensorEntity):
    """Check if there is any error message from system."""

    def __init__(self, error: Error):
        """Init."""
        self._error = error
        super().__init__(
            DOMAIN,
            DEVICE_CLASS_PROBLEM,
            "error_" + error.status_code,
            error.title,
            False,
        )

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            "status_code": self._error.status_code,
            "title": self._error.title,
            "timestamp": self._error.timestamp,
            "description": self._error.description,
            "device_name": self._error.device_name,
        }

    async def vaillant_update(self):
        """Update specific for vaillant.

        Special attention during the update, the entity can remove itself
        from registry if the error disappear from vaillant system.
        """
        errors = {e.status_code: e for e in self.hub.system.errors}

        if self._error.status_code in [e.status_code for e in list(errors.values())]:
            self._error = errors.get(self._error.status_code)
        else:
            self.hass.async_create_task(self._remove())

    async def _remove(self):
        """Remove entity itself."""
        await self.async_remove()

        reg = await self.hass.helpers.entity_registry.async_get_registry()
        entity_id = reg.async_get_entity_id(DOMAIN, VAILLANT, self.unique_id)
        if entity_id:
            reg.async_remove(entity_id)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return True


class HolidayModeSensor(VaillantEntity, BinarySensorEntity):
    """Binary sensor for holiday mode."""

    def __init__(self, holiday_mode: HolidayMode):
        """Init."""
        super().__init__(DOMAIN, DEVICE_CLASS_POWER, "holiday", "holiday", False)
        self._holiday = holiday_mode

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._holiday is not None and self._holiday.is_applied

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.is_on:
            return {
                "start_date": self._holiday.start_date.isoformat(),
                "end_date": self._holiday.end_date.isoformat(),
                "temperature": self._holiday.target,
            }
        return {}

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._holiday = self.hub.system.holiday


class QuickModeSensor(VaillantEntity, BinarySensorEntity):
    """Binary sensor for holiday mode."""

    def __init__(self, quick_mode: QuickMode):
        """Init."""
        super().__init__(DOMAIN, DEVICE_CLASS_POWER, "quick_mode", "quick_mode", False)
        self._quick_mode = quick_mode

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._quick_mode is not None

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.is_on:
            return {"quick_mode": self._quick_mode.name}
        return {}

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._quick_mode = self.hub.system.quick_mode
