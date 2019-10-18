"""Interfaces with Vaillant binary sensors."""

import logging
from abc import ABC

from pymultimatic.model import Room, Circulation, Device, BoilerStatus, Error, \
    SystemStatus, HolidayMode, QuickMode

from homeassistant.components.binary_sensor import BinarySensorDevice, DOMAIN, \
    DEVICE_CLASS_WINDOW, DEVICE_CLASS_LOCK, DEVICE_CLASS_CONNECTIVITY,\
    DEVICE_CLASS_PROBLEM, DEVICE_CLASS_POWER, DEVICE_CLASS_BATTERY
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.util import Throttle
from . import CONF_BINARY_SENSOR_BOILER_ERROR, \
    CONF_BINARY_SENSOR_CIRCULATION, \
    CONF_BINARY_SENSOR_SYSTEM_ONLINE, CONF_BINARY_SENSOR_SYSTEM_UPDATE, \
    CONF_BINARY_SENSOR_ROOM_WINDOW, CONF_BINARY_SENSOR_ROOM_CHILD_LOCK, \
    CONF_BINARY_SENSOR_DEVICE_BATTERY, CONF_BINARY_SENSOR_DEVICE_RADIO_REACH, \
    BaseVaillantEntity, HUB, DOMAIN as VAILLANT, \
    CONF_BINARY_SENSOR_SYSTEM_ERRORS, CONF_BINARY_SENSOR_HOLIDAY_MODE, \
    CONF_BINARY_SENSOR_QUICK_MODE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Vaillant binary sensor platform."""
    sensors = []
    hub = hass.data[HUB]
    if hub.system:
        if hub.system.circulation \
                and hub.config[CONF_BINARY_SENSOR_CIRCULATION]:
            sensors.append(
                VaillantCirculation(hub.system.circulation))

        if hub.system.boiler_status:
            if hub.config[CONF_BINARY_SENSOR_BOILER_ERROR]:
                sensors.append(
                    VaillantBoilerError(hub.system.boiler_status))

        if hub.system.system_status:
            if hub.config[CONF_BINARY_SENSOR_SYSTEM_ONLINE]:
                sensors.append(
                    VaillantBoxOnline(hub.system.system_status))
            if hub.config[CONF_BINARY_SENSOR_SYSTEM_UPDATE]:
                sensors.append(
                    VaillantBoxUpdate(hub.system.system_status))

        for room in hub.system.rooms:
            if hub.config[CONF_BINARY_SENSOR_ROOM_WINDOW]:
                sensors.append(VaillantWindow(room))
            if hub.config[CONF_BINARY_SENSOR_ROOM_CHILD_LOCK]:
                sensors.append(VaillantChildLock(room))
            for device in room.devices:
                if hub.config[CONF_BINARY_SENSOR_DEVICE_BATTERY]:
                    sensors.append(
                        VaillantRoomDeviceBattery(device, room))
                if hub.config[CONF_BINARY_SENSOR_DEVICE_RADIO_REACH]:
                    sensors.append(
                        VaillantRoomDeviceConnectivity(device, room))
        if hub.config[CONF_BINARY_SENSOR_HOLIDAY_MODE]:
            entity = VaillantHolidayMode(hub.system.holiday_mode)
            hub.add_listener(entity)
            sensors.append(entity)

        if hub.config[CONF_BINARY_SENSOR_QUICK_MODE]:
            entity = VaillantQuickMode(hub.system.quick_mode)
            hub.add_listener(entity)
            sensors.append(entity)

        if hub.config[CONF_BINARY_SENSOR_SYSTEM_ERRORS]:
            handler = \
                VaillantSystemErrorHandler(hub, hass, async_add_entities,
                                           hub.config[CONF_SCAN_INTERVAL])
            await handler.update()

    _LOGGER.info("Adding %s binary sensor entities", len(sensors))

    async_add_entities(sensors)
    return True


class VaillantCirculation(BaseVaillantEntity, BinarySensorDevice):
    """Binary sensor for circulation running on or not."""

    def __init__(self, circulation: Circulation):
        """Initialize entity."""
        super().__init__(DOMAIN, DEVICE_CLASS_POWER, circulation.name,
                         circulation.name, False)
        self._circulation = circulation

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        from pymultimatic.model import OperatingModes, SettingModes, QuickModes

        active_mode = self._circulation.active_mode
        return active_mode.current_mode == OperatingModes.ON \
            or active_mode.sub_mode == SettingModes.ON \
            or active_mode == QuickModes.HOTWATER_BOOST

    @property
    def available(self):
        """Return True if entity is available."""
        return self._circulation is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        new_circulation = self.hub.find_component(self._circulation)

        if new_circulation:
            _LOGGER.debug("New / old state: %s / %s",
                          new_circulation.active_mode.current_mode,
                          self._circulation.active_mode.current_mode)
        else:
            _LOGGER.debug("Circulation %s doesn't exist anymore",
                          self._circulation.id)
        self._circulation = new_circulation


class VaillantWindow(BaseVaillantEntity, BinarySensorDevice):
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
            _LOGGER.debug("New / old state: %s / %s", new_room.child_lock,
                          self._room.child_lock)
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room


class VaillantChildLock(BaseVaillantEntity, BinarySensorDevice):
    """Binary sensor for valve child lock."""

    def __init__(self, room: Room):
        """Initialize entity."""
        super().__init__(DOMAIN, DEVICE_CLASS_LOCK, room.name, room.name)
        self._room = room

    @property
    def available(self):
        """Return True if entity is available."""
        return self._room is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        new_room: Room = self.hub.find_component(self._room)

        if new_room:
            _LOGGER.debug("New / old state: %s / %s", new_room.child_lock,
                          self._room.child_lock)
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room

    @property
    def is_on(self):
        """According to the doc, true means unlock, false lock."""
        return not self._room.child_lock


class VaillantRoomDevice(BaseVaillantEntity, BinarySensorDevice, ABC):
    """Base class for device in room."""

    def __init__(self, device: Device, room: Room, device_class):
        """Initialize entity."""
        super().__init__(DOMAIN, device_class, device.sgtin, device.name)
        self._room = room
        self._device = device
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
        return self._device is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        new_room: Room = self.hub.find_component(self._room)
        new_device: Device = self._find_device(new_room, self._device.sgtin)

        if new_room:
            if new_device:
                _LOGGER.debug("New / old state: %s / %s",
                              new_device.battery_low, self._device.battery_low)
            else:
                _LOGGER.debug("Device %s doesn't exist anymore",
                              self._device.sgtin)
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room
        self._device = new_device


class VaillantRoomDeviceBattery(VaillantRoomDevice):
    """Represent a device battery."""

    def __init__(self, device: Device, room: Room):
        """Initialize entity."""
        super().__init__(device, room, DEVICE_CLASS_BATTERY)

    @property
    def is_on(self):
        """According to the doc, true means normal, false low."""
        return self._device.battery_low


class VaillantRoomDeviceConnectivity(VaillantRoomDevice):
    """Device in room is out of reach or not."""

    def __init__(self, device: Device, room: Room):
        """Initialize entity."""
        super().__init__(device, room, DEVICE_CLASS_CONNECTIVITY)

    @property
    def is_on(self):
        """According to the doc, true means connected, false disconnected."""
        return not self._device.radio_out_of_reach


class BaseVaillantSystem(BaseVaillantEntity, BinarySensorDevice):
    """Base class for system wide binary sensor."""

    def __init__(self, device_class, system_status: SystemStatus, name,
                 comp_id):
        """Initialize entity."""
        super().__init__(DOMAIN, device_class, name, comp_id, False)
        self._system_status = system_status

    @property
    def available(self):
        """Return True if entity is available."""
        return self._system_status is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        system_status: SystemStatus = self.hub.system.system_status

        if system_status:
            _LOGGER.debug(
                "Found new system status "
                "online? %s, up to date? %s", system_status.is_online,
                system_status.is_up_to_date)
        else:
            _LOGGER.debug("System status doesn't exist anymore")
        self._system_status = system_status


class VaillantBoxUpdate(BaseVaillantSystem):
    """Update binary sensor."""

    def __init__(self, system_status: SystemStatus):
        """Init."""
        super().__init__(DEVICE_CLASS_POWER, system_status, 'System update',
                         'system_update')

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return not self._system_status.is_up_to_date


class VaillantBoxOnline(BaseVaillantSystem):
    """Check if box is online."""

    def __init__(self, system_status: SystemStatus):
        """Init"""
        super().__init__(DEVICE_CLASS_CONNECTIVITY, system_status,
                         'System Online', 'system_online')

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._system_status.is_online


class VaillantBoilerError(BaseVaillantEntity, BinarySensorDevice):
    """Check if there is some error."""

    async def vaillant_update(self):
        """Update specific for vaillant."""
        _LOGGER.debug("new boiler status is %s", self.hub.system.boiler_status)
        self._boiler_status = self.hub.system.boiler_status

    def __init__(self, boiler_status: BoilerStatus):
        """Initialize entity."""
        super().__init__(DOMAIN, DEVICE_CLASS_PROBLEM,
                         boiler_status.device_name, boiler_status.device_name,
                         False)
        self._boiler_status = boiler_status

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._boiler_status is not None and self._boiler_status.is_error

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            'status_code': self._boiler_status.status_code,
            'title': self._boiler_status.title,
            'timestamp': self._boiler_status.timestamp
        }


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
                binary_sensor = \
                    VaillantSystemError(error)
                if not reg.async_is_registered(binary_sensor.entity_id):
                    sensors.append(binary_sensor)

            if sensors:
                self._async_add_entities(sensors)


class VaillantSystemError(BaseVaillantEntity, BinarySensorDevice):
    """Check if there is any error message from system."""

    def __init__(self, error: Error):
        """Init."""
        self._error = error
        super().__init__(DOMAIN, DEVICE_CLASS_PROBLEM, error.status_code,
                         error.title, False)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            'status_code': self._error.status_code,
            'title': self._error.title,
            'timestamp': self._error.timestamp,
            'description': self._error.description,
            'device_name': self._error.device_name
        }

    async def vaillant_update(self):
        """Update specific for vaillant.

        Special attention during the update, the entity can remove itself
        from registry if the error disappear from vaillant system.
        """
        errors = {e.status_code: e for e in self.hub.system.errors}

        if self._error.status_code in [e.status_code for e in
                                       list(errors.values())]:
            self._error = errors.get(self._error.status_code)
        else:
            self.hass.async_create_task(self._remove())

    async def _remove(self):
        """Remove entity itself."""
        await self.async_remove()

        reg = await self.hass.helpers.entity_registry.async_get_registry()
        entity_id = reg.async_get_entity_id(
            DOMAIN,
            VAILLANT,
            self.unique_id
        )
        if entity_id:
            reg.async_remove(entity_id)


class VaillantHolidayMode(BaseVaillantEntity, BinarySensorDevice):
    """Binary sensor for holiday mode"""

    def __init__(self, holiday_mode: HolidayMode):
        """Init."""
        super().__init__(DOMAIN, DEVICE_CLASS_POWER, 'holiday', 'holiday',
                         False)
        self._holiday = holiday_mode

    @property
    def is_on(self):
        return self._holiday is not None and self._holiday.is_applied

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.is_on:
            return {
                'start_date': self._holiday.start_date.isoformat(),
                'end_date': self._holiday.end_date.isoformat(),
                'temperature': self._holiday.target_temperature,
            }
        return {}

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._holiday = self.hub.system.holiday_mode


class VaillantQuickMode(BaseVaillantEntity, BinarySensorDevice):
    """Binary sensor for holiday mode"""

    def __init__(self, quick_mode: QuickMode):
        """Init."""
        super().__init__(DOMAIN, DEVICE_CLASS_POWER, 'quick_mode',
                         'quick_mode', False)
        self._quick_mode = quick_mode

    @property
    def is_on(self):
        return self._quick_mode is not None

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.is_on:
            return {
                'quick_mode': self._quick_mode.name
            }
        return {}

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._quick_mode = self.hub.system.quick_mode
