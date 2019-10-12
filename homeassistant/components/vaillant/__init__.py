"""Vaillant component."""
import abc
from abc import ABC

import logging
from datetime import timedelta
from typing import Optional

import voluptuous as vol

from homeassistant.const import (CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_USERNAME)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, slugify
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vaillant'
HUB = '{}_HUB'.format(DOMAIN)

PLATFORMS = [
    'binary_sensor',
    'sensor',
    'climate',
    'water_heater'
]

CONF_SMARTPHONE_ID = 'smartphoneid'
CONF_QUICK_VETO_DURATION = 'quick_veto_duration'
CONF_BINARY_SENSOR_CIRCULATION = 'binary_sensor_circulation'
CONF_BINARY_SENSOR_BOILER_ERROR = 'binary_sensor_boiler_error'
CONF_BINARY_SENSOR_SYSTEM_ONLINE = 'binary_sensor_system_online'
CONF_BINARY_SENSOR_SYSTEM_UPDATE = 'binary_sensor_system_update'
CONF_BINARY_SENSOR_ROOM_WINDOW = 'binary_sensor_room_window'
CONF_BINARY_SENSOR_ROOM_CHILD_LOCK = 'binary_sensor_room_child_lock'
CONF_BINARY_SENSOR_DEVICE_BATTERY = 'binary_sensor_device_battery'
CONF_BINARY_SENSOR_DEVICE_RADIO_REACH = 'binary_sensor_device_radio_reach'
CONF_BINARY_SENSOR_SYSTEM_ERRORS = 'binary_sensor_system_errors'
CONF_SENSOR_BOILER_WATER_TEMPERATURE = 'sensor_boiler_water_temperature'
CONF_SENSOR_BOILER_WATER_PRESSURE = 'sensor_boiler_water_pressure'
CONF_SENSOR_ROOM_TEMPERATURE = 'sensor_room_temperature'
CONF_SENSOR_ZONE_TEMPERATURE = 'sensor_zone_temperature'
CONF_SENSOR_OUTDOOR_TEMPERATURE = 'sensor_outdoor_temperature'
CONF_SENSOR_HOT_WATER_TEMPERATURE = 'sensor_hot_water_temperature'
CONF_WATER_HEATER = 'water_heater'
CONF_ROOM_CLIMATE = 'room_climate'
CONF_ZONE_CLIMATE = 'zone_climate'

DEFAULT_EMPTY = ''
MIN_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
DEFAULT_SMART_PHONE_ID = 'homeassistant'
DEFAULT_QUICK_VETO_DURATION = 3 * 60
QUICK_VETO_MIN_DURATION = 0.5 * 60
QUICK_VETO_MAX_DURATION = 24 * 60

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): (
            vol.All(cv.time_period, vol.Clamp(min=MIN_SCAN_INTERVAL))),
        vol.Optional(CONF_SMARTPHONE_ID,
                     default=DEFAULT_SMART_PHONE_ID): cv.string,
        vol.Optional(CONF_QUICK_VETO_DURATION,
                     default=DEFAULT_QUICK_VETO_DURATION):
        (vol.All(cv.positive_int, vol.Clamp(min=QUICK_VETO_MIN_DURATION,
                                            max=QUICK_VETO_MAX_DURATION))),
        vol.Optional(CONF_BINARY_SENSOR_CIRCULATION, default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR_BOILER_ERROR,
                     default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR_SYSTEM_ONLINE,
                     default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR_SYSTEM_UPDATE,
                     default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR_ROOM_WINDOW, default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR_ROOM_CHILD_LOCK,
                     default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR_DEVICE_BATTERY,
                     default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR_DEVICE_RADIO_REACH,
                     default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR_SYSTEM_ERRORS,
                     default=True): cv.boolean,
        vol.Optional(CONF_SENSOR_BOILER_WATER_TEMPERATURE,
                     default=True): cv.boolean,
        vol.Optional(CONF_SENSOR_BOILER_WATER_PRESSURE,
                     default=True): cv.boolean,
        vol.Optional(CONF_SENSOR_ROOM_TEMPERATURE, default=True): cv.boolean,
        vol.Optional(CONF_SENSOR_ZONE_TEMPERATURE, default=True): cv.boolean,
        vol.Optional(CONF_SENSOR_OUTDOOR_TEMPERATURE,
                     default=True): cv.boolean,
        vol.Optional(CONF_SENSOR_HOT_WATER_TEMPERATURE,
                     default=True): cv.boolean,
        vol.Optional(CONF_WATER_HEATER, default=True): cv.boolean,
        vol.Optional(CONF_ROOM_CLIMATE, default=True): cv.boolean,
        vol.Optional(CONF_ZONE_CLIMATE, default=True): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_VAILLANT_MODE = 'vaillant_mode'


async def async_setup(hass, config):
    """Set up vaillant component."""
    hub = VaillantHub(config[DOMAIN])
    hass.data[HUB] = hub

    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(hass, platform, DOMAIN, {}, config))

    _LOGGER.info("Successfully initialized")

    return True


class VaillantHub:
    """Vaillant entry point for home-assistant."""

    def __init__(self, config):
        """Initialize hub."""
        from pymultimatic.model import System
        from pymultimatic.systemmanager import SystemManager

        self._manager = SystemManager(config[CONF_USERNAME],
                                      config[CONF_PASSWORD],
                                      config[CONF_SMARTPHONE_ID])

        self._listeners = []
        self.system: System = self._manager.get_system()
        self._quick_veto_duration = config[CONF_QUICK_VETO_DURATION]
        self.config = config
        self.update_system = Throttle(
            config[CONF_SCAN_INTERVAL])(self._update_system)

    def _update_system(self):
        """Fetch vaillant system."""
        try:
            self._manager.request_hvac_update()
            self.system = self._manager.get_system()
            _LOGGER.debug("update_system successfully fetched")
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception("Enable to fetch data from vaillant API")
            # update_system can is called by all entities, if it fails for
            # one entity, it will certainly fail for others.
            # catching exception so the throttling is occurring

    def find_component(self, comp):
        """Find a component in the system with the given id, no IO is done."""
        from pymultimatic.model import Zone, Room, HotWater, Circulation

        if isinstance(comp, Zone):
            return [zone for zone in self.system.zones
                    if zone.id == comp.id][0]
        if isinstance(comp, Room):
            return [room for room in self.system.rooms
                    if room.id == comp.id][0]
        if isinstance(comp, HotWater):
            if self.system.hot_water and self.system.hot_water.id == comp.id:
                return self.system.hot_water
        if isinstance(comp, Circulation):
            if self.system.circulation \
                    and self.system.circulation.id == comp.id:
                return self.system.circulation

        return None

    def add_listener(self, listener):
        """Add an entity in listener list."""
        self._listeners.append(listener)

    def _refresh_listening_entities(self):
        """Force refresh of all listening entities and fetch vaillant data."""
        self.update_system(no_throttle=True)
        for listener in self._listeners:
            listener.async_schedule_update_ha_state(True)

    def set_hot_water_target_temperature(self, entity, hot_water,
                                         target_temperature):
        """Set hot water target temperature."""
        self._manager\
            .set_hot_water_setpoint_temperature(hot_water.id,
                                                target_temperature)

        self.system.hot_water = self._manager.get_hot_water(hot_water.id)
        entity.async_schedule_update_ha_state(True)

    def set_room_target_temperature(self, entity, room, target_temperature):
        """Set target temperature for a room.

        If the room is in MANUAL mode, simply modify the target temperature,
        if the room is not in MANUAL mode, create à quick veto. Changing target
        temperature while not on MANUAL mode, will result in switching the room
        to manual mode indefinitely."""
        from pymultimatic.model import OperatingModes, QuickVeto

        mode = self.system.get_active_mode_room(room)

        if mode.current_mode != OperatingModes.MANUAL:
            veto = QuickVeto(self._quick_veto_duration, target_temperature)
            self._manager.set_room_quick_veto(room.id, veto)
        else:
            self._manager\
                .set_room_setpoint_temperature(room.id, target_temperature)

        self.system.set_room(room.id, self._manager.get_room(room))
        entity.async_schedule_update_ha_state(True)

    def set_zone_target_temperature(self, entity, zone, target_temperature):
        """Set target temperature for a zone.
        If the zone is running DAY mode (= fixed target temperature), simply
        change the target temperature.
        Otherwise, create a quick veto."""
        from pymultimatic.model import OperatingModes, QuickVeto

        mode = self.system.get_active_mode_zone(zone)

        if mode.current_mode != OperatingModes.DAY:
            veto = QuickVeto(self._quick_veto_duration, target_temperature)
            self._manager.set_zone_quick_veto(zone.id, veto)
        else:
            self._manager\
                .set_zone_setpoint_temperature(zone.id, target_temperature)

        self.system.set_zone(zone.id, self._manager.get_zone(zone))
        entity.async_schedule_update_ha_state(True)

    def set_zone_target_high_temperature(self, entity, zone, temperature):
        """Set high target temperature for a zone."""
        self._manager.set_zone_setpoint_temperature(zone.id, temperature)
        self.system.set_zone(zone.id, self._manager.get_zone(zone))
        entity.async_schedule_update_ha_state(True)

    def set_zone_target_low_temperature(self, entity, zone, temperature):
        """Set low temperature for a zone."""
        self._manager.set_zone_setback_temperature(zone.id, temperature)
        self.system.set_zone(zone.id, self._manager.get_zone(zone.id))
        entity.async_schedule_update_ha_state(True)

    def set_hot_water_operating_mode(self, entity, hot_water, mode):
        """Set hot water operation mode."""
        was_quick_mode = self._set_quick_mode(mode)

        if not was_quick_mode:
            self._manager.set_hot_water_operating_mode(hot_water.id, mode)
            self.system.hot_water = self._manager.get_hot_water(hot_water.id)
            entity.async_schedule_update_ha_state(True)

    def set_room_operating_mode(self, entity, room, mode):
        """Set room operation mode."""
        was_quick_mode = self._set_quick_mode(mode)

        if not was_quick_mode:
            self._manager.set_room_operating_mode(room.id, mode)
            self.system.set_room(room.id, self._manager.get_room(room.id))
            entity.async_schedule_update_ha_state(True)

    def set_zone_operating_mode(self, entity, zone, mode):
        """Set zone operation mode."""
        was_quick_mode = self._set_quick_mode(mode)

        if not was_quick_mode:
            self._manager.set_zone_operating_mode(zone.id, mode)
            self.system.set_zone(zone.id, self._manager.get_zone(zone.id))
            entity.async_schedule_update_ha_state(True)

    def _set_quick_mode(self, quick_mode):
        """Set quick mode, it may impact the whole system."""
        from pymultimatic.model import QuickMode

        if isinstance(quick_mode, QuickMode):
            _LOGGER.debug('Mode %s is a quick mode', quick_mode)
            self._manager.set_quick_mode(quick_mode)
            self._refresh_listening_entities()
            return True
        return False


class BaseVaillantEntity(Entity, ABC):
    """Define base class for vaillant."""

    def __init__(self, domain, device_class, comp_id, comp_name):
        """Initialize entity."""
        self._device_class = device_class
        if device_class:
            id_format = domain + '.' + DOMAIN + '_{}_' + device_class
        else:
            id_format = domain + '.' + DOMAIN + '_{}'

        self.entity_id = id_format\
            .format(slugify(comp_id)).replace(' ', '_').lower()
        self._vaillant_name = comp_name
        self.hub = None

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._vaillant_name

    async def async_update(self):
        """Update the entity."""
        _LOGGER.debug("Time to update %s", self.entity_id)
        if not self.hub:
            self.hub = self.hass.data[HUB]
        self.hub.update_system()

        await self.vaillant_update()

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @abc.abstractmethod
    async def vaillant_update(self):
        """Update specific for vaillant."""
        pass
