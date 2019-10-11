"""Interfaces with Vaillant binary sensors."""

import logging
from abc import ABC

from vr900connector.model import Room, Circulation, Device, BoilerStatus, \
    SystemErrorMessage

from homeassistant.components.binary_sensor import BinarySensorDevice, DOMAIN
from homeassistant.const import DEVICE_CLASS_POWER, DEVICE_CLASS_BATTERY, \
    CONF_SCAN_INTERVAL
from homeassistant.util import Throttle
from . import CONF_BINARY_SENSOR_BOILER_ERROR, \
    CONF_BINARY_SENSOR_CIRCULATION, \
    CONF_BINARY_SENSOR_SYSTEM_ONLINE, CONF_BINARY_SENSOR_SYSTEM_UPDATE, \
    CONF_BINARY_SENSOR_ROOM_WINDOW, CONF_BINARY_SENSOR_ROOM_CHILD_LOCK, \
    CONF_BINARY_SENSOR_DEVICE_BATTERY, CONF_BINARY_SENSOR_DEVICE_RADIO_REACH, \
    BaseVaillantEntity, HUB, DOMAIN as VAILLANT, \
    CONF_BINARY_SENSOR_SYSTEM_ERRORS

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_WINDOW = 'window'
DEVICE_CLASS_LOCK = 'lock'
DEVICE_CLASS_CONNECTIVITY = 'connectivity'
DEVICE_CLASS_PROBLEM = 'problem'


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Vaillant binary sensor platform."""
    sensors = []
    hub = hass.data[HUB]
    if hub.system:
        if hub.system.circulation \
                and hub.config[CONF_BINARY_SENSOR_CIRCULATION]:
            sensors.append(
                VaillantCirculationBinarySensor(hub.system.circulation))

        if hub.system.boiler_status:
            if hub.config[CONF_BINARY_SENSOR_BOILER_ERROR]:
                sensors.append(
                    VaillantBoilerErrorBinarySensor(hub.system.boiler_status))
            if hub.config[CONF_BINARY_SENSOR_SYSTEM_ONLINE]:
                sensors.append(
                    VaillantBoxOnlineBinarySensor(hub.system.boiler_status))
            if hub.config[CONF_BINARY_SENSOR_SYSTEM_UPDATE]:
                sensors.append(
                    VaillantBoxUpdateBinarySensor(hub.system.boiler_status))

        for room in hub.system.rooms:
            if hub.config[CONF_BINARY_SENSOR_ROOM_WINDOW]:
                sensors.append(VaillantWindowBinarySensor(room))
            if hub.config[CONF_BINARY_SENSOR_ROOM_CHILD_LOCK]:
                sensors.append(VaillantChildLockBinarySensor(room))
            for device in room.devices:
                if hub.config[CONF_BINARY_SENSOR_DEVICE_BATTERY]:
                    sensors.append(
                        VaillantRoomDeviceBatteryBinarySensor(device, room))
                if hub.config[CONF_BINARY_SENSOR_DEVICE_RADIO_REACH]:
                    sensors.append(
                        VaillantRoomDeviceConnectivityBinarySensor(device,
                                                                   room))
        if hub.config[CONF_BINARY_SENSOR_SYSTEM_ERRORS]:
            handler = \
                VaillantSystemBinarySensorHandler(
                    hub, hass,  async_add_entities,
                    hub.config[CONF_SCAN_INTERVAL])
            await handler.update()

    _LOGGER.info("Adding %s binary sensor entities", len(sensors))

    async_add_entities(sensors)
    return True


class VaillantCirculationBinarySensor(BaseVaillantEntity, BinarySensorDevice):
    """Binary sensor for circulation running on or not."""

    def __init__(self, circulation: Circulation):
        """Initialize entity."""
        super().__init__(DOMAIN, DEVICE_CLASS_POWER, circulation.name,
                         circulation.name)
        self._circulation = circulation

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        from vr900connector.model import HeatingMode, QuickMode

        active_mode = self._circulation.active_mode
        return active_mode.current_mode == HeatingMode.ON \
            or active_mode.sub_mode == HeatingMode.ON \
            or active_mode == QuickMode.QM_HOTWATER_BOOST

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


class VaillantWindowBinarySensor(BaseVaillantEntity, BinarySensorDevice):
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


class VaillantChildLockBinarySensor(BaseVaillantEntity, BinarySensorDevice):
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


class VaillantRoomDeviceBinarySensor(BaseVaillantEntity, BinarySensorDevice,
                                     ABC):
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


class VaillantRoomDeviceBatteryBinarySensor(VaillantRoomDeviceBinarySensor):
    """Represent a device battery."""

    def __init__(self, device: Device, room: Room):
        """Initialize entity."""
        super().__init__(device, room, DEVICE_CLASS_BATTERY)

    @property
    def is_on(self):
        """According to the doc, true means normal, false low."""
        return self._device.battery_low


class VaillantRoomDeviceConnectivityBinarySensor\
        (VaillantRoomDeviceBinarySensor):
    """Device in room is out of reach or not."""

    def __init__(self, device: Device, room: Room):
        """Initialize entity."""
        super().__init__(device, room, DEVICE_CLASS_CONNECTIVITY)

    @property
    def is_on(self):
        """According to the doc, true means connected, false disconnected."""
        return not self._device.radio_out_of_reach


class BaseVaillantSystemBinarySensor(BaseVaillantEntity, BinarySensorDevice):
    """Base class for system wide binary sensor."""

    def __init__(self, device_class, boiler_status: BoilerStatus):
        """Initialize entity."""
        super().__init__(DOMAIN, device_class, boiler_status.device_name,
                         boiler_status.device_name)
        self._boiler_status = boiler_status

    @property
    def available(self):
        """Return True if entity is available."""
        return self._boiler_status is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        boiler_status: BoilerStatus = self.hub.system.boiler_status

        if boiler_status:
            _LOGGER.debug(
                "Found new boiler status error? %s, "
                "online? %s, up to date? %s", boiler_status.is_error,
                boiler_status.is_online, boiler_status.is_up_to_date)
        else:
            _LOGGER.debug("Boiler status doesn't exist anymore")
        self._boiler_status = boiler_status


class VaillantBoxUpdateBinarySensor(BaseVaillantSystemBinarySensor):
    """Update binary sensor."""

    def __init__(self, boiler_status: BoilerStatus):
        """Return True if entity is available."""
        super().__init__(DEVICE_CLASS_POWER, boiler_status)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return not self._boiler_status.is_up_to_date


class VaillantBoxOnlineBinarySensor(BaseVaillantSystemBinarySensor):
    """Check if box is online."""

    def __init__(self, boiler_status: BoilerStatus):
        """Return True if entity is available."""
        super().__init__(DEVICE_CLASS_CONNECTIVITY, boiler_status)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._boiler_status.is_online


class VaillantBoilerErrorBinarySensor(BaseVaillantSystemBinarySensor):
    """Check if there is some error."""

    def __init__(self, boiler_status: BoilerStatus):
        """Initialize entity."""
        super().__init__(DEVICE_CLASS_PROBLEM, boiler_status)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._boiler_status.is_error

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            'code': self._boiler_status.code,
            'title': self._boiler_status.title,
            'last_update': self._boiler_status.last_update
        }


class VaillantSystemBinarySensorHandler:

    def __init__(self, hub, hass, async_add_entities, scan_interval) -> None:
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
                    VaillantSystemErrorBinarySensor(error)
                if not reg.async_is_registered(binary_sensor.entity_id):
                    sensors.append(binary_sensor)

            if sensors:
                self._async_add_entities(sensors)


class VaillantSystemErrorBinarySensor(BaseVaillantEntity, BinarySensorDevice):
    """Check if there is any error message from system."""

    def __init__(self, error: SystemErrorMessage):
        self.error = error
        super().__init__(DOMAIN, DEVICE_CLASS_PROBLEM, error.status_code,
                         error.title)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            'status_code': self.error.status_code,
            'title': self.error.title,
            'timestamp': self.error.timestamp,
            'description': self.error.description,
            'device_name': self.error.device_name
        }

    async def vaillant_update(self):
        errors = {e.status_code: e for e in self.hub.system.errors}

        if self.error.status_code in [e.status_code for e in errors.values()]:
            self.error = errors.get(self.error.status_code)
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
