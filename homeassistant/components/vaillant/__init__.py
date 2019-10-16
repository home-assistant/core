"""Vaillant component."""
import abc
from abc import ABC

import logging
from datetime import timedelta, datetime

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
ATTR_QUICK_VETO_END = 'quick_veto_end'
ATTR_QUICK_MODE = 'quick_mode'
ATTR_START_DATE = 'start_date'
ATTR_END_DATE = 'end_date'
ATTR_TEMPERATURE = 'temperature'

QUICK_MODES_LIST = ['QM_HOTWATER_BOOST', 'QM_VENTILATION_BOOST', 'QM_PARTY',
                    'QM_ONE_DAY_AWAY', 'QM_SYSTEM_OFF', 'QM_ONE_DAY_AT_HOME']

# Services
SERVICE_REMOVE_QUICK_MODE = "remove_quick_mode"
SERVICE_REMOVE_HOLIDAY_MODE = "remove_holiday_mode"
SERVICE_SET_QUICK_MODE = "set_quick_mode"
SERVICE_SET_HOLIDAY_MODE = "set_holiday_mode"

SERVICE_REMOVE_QUICK_MODE_SCHEMA = vol.Schema({})
SERVICE_REMOVE_HOLIDAY_MODE_SCHEMA = vol.Schema({})
SERVICE_SET_QUICK_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_QUICK_MODE): vol.All(
            vol.Coerce(str), vol.In(QUICK_MODES_LIST)
        )
    }
)
SERVICE_SET_HOLIDAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_START_DATE): vol.All(
            vol.Coerce(str)
        ),
        vol.Required(ATTR_END_DATE): vol.All(
            vol.Coerce(str)
        ),
        vol.Required(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(float), vol.Clamp(min=5, max=30)
        )
    }
)

SERVICE_TO_METHOD = {
    SERVICE_REMOVE_QUICK_MODE: {
        "method": SERVICE_REMOVE_QUICK_MODE,
        "schema": SERVICE_REMOVE_QUICK_MODE_SCHEMA,
    },
    SERVICE_REMOVE_HOLIDAY_MODE: {
        "method": SERVICE_REMOVE_HOLIDAY_MODE,
        "schema": SERVICE_REMOVE_HOLIDAY_MODE_SCHEMA,
    },
    SERVICE_SET_QUICK_MODE: {
        "method": SERVICE_SET_QUICK_MODE,
        "schema": SERVICE_SET_QUICK_MODE_SCHEMA,
    },
    SERVICE_SET_HOLIDAY_MODE: {
        "method": SERVICE_SET_HOLIDAY_MODE,
        "schema": SERVICE_SET_HOLIDAY_MODE_SCHEMA,
    },
}


async def async_setup(hass, config):
    """Set up vaillant component."""
    hub = VaillantHub(config[DOMAIN])
    hass.data[HUB] = hub

    service_handler = VaillantServiceHandler(hub)

    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(hass, platform, DOMAIN, {}, config))

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service]["schema"]
        hass.services.async_register(
            DOMAIN, service, service_handler.async_handle, schema=schema
        )

    _LOGGER.info("Successfully initialized")

    return True


class VaillantHub:
    """Vaillant entry point for home-assistant."""

    def __init__(self, config):
        """Initialize hub."""
        from pymultimatic.model import System
        from pymultimatic.systemmanager import SystemManager

        self.manager = SystemManager(config[CONF_USERNAME],
                                     config[CONF_PASSWORD],
                                     config[CONF_SMARTPHONE_ID])

        self._listeners = []
        self.system: System = self.manager.get_system()
        self._quick_veto_duration = config[CONF_QUICK_VETO_DURATION]
        self.config = config
        self.update_system = Throttle(
            config[CONF_SCAN_INTERVAL])(self._update_system)

    def _update_system(self):
        """Fetch vaillant system."""
        try:
            self.manager.request_hvac_update()
            self.system = self.manager.get_system()
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

    def refresh_listening_entities(self):
        """Force refresh of all listening entities and fetch vaillant data."""
        self.update_system(no_throttle=True)
        for listener in self._listeners:
            listener.async_schedule_update_ha_state(True)

    def set_hot_water_target_temperature(self, entity, hot_water,
                                         target_temp):
        """Set hot water target temperature.

        If dhw is in ON mode, simply modify the target temperature, otherwise
        setting mode to ON and changing the target temperature.

        If there is a quick mode that impact dhw running on, remove it."""
        from pymultimatic.model import OperatingModes

        touch_quick_mode = False
        if self.system.quick_mode is not None and \
                self.system.quick_mode.for_dhw:
            self.manager.remove_quick_mode()
            touch_quick_mode = True
            self.system.quick_mode = None

        active_mode = self.system.get_active_mode_hot_water(hot_water)

        if active_mode.current_mode != OperatingModes.ON:
            self.manager.set_hot_water_operating_mode(hot_water.id,
                                                      OperatingModes.ON)
        self.manager\
            .set_hot_water_setpoint_temperature(hot_water.id, target_temp)

        if touch_quick_mode:
            self.refresh_listening_entities()
        else:
            self.system.hot_water = self.manager.get_hot_water(hot_water.id)
        entity.async_schedule_update_ha_state(True)

    def set_room_target_temperature(self, entity, room, target_temp):
        """Set target temperature for a room.

        If the room is in MANUAL mode, simply modify the target temperature,
        if the room is not in MANUAL mode, create à quick veto.

        If there is a quick mode that impact room running on, remove it.
        """
        from pymultimatic.model import OperatingModes, QuickVeto

        touch_quick_mode = False
        if self.system.quick_mode is not None and \
                self.system.quick_mode.for_room:
            self.manager.remove_quick_mode()
            touch_quick_mode = True
            self.system.quick_mode = None

        active_mode = self.system.get_active_mode_room(room)

        if active_mode.current_mode == OperatingModes.MANUAL:
            self.manager.set_room_setpoint_temperature(room.id, target_temp)
        else:
            veto = QuickVeto(self._quick_veto_duration, target_temp)
            self.manager.set_room_quick_veto(room.id, veto)

        if touch_quick_mode:
            self.refresh_listening_entities()
        else:
            self.system.set_room(room.id, self.manager.get_room(room.id))
            entity.async_schedule_update_ha_state(True)

    def set_zone_target_temperature(self, entity, zone, target_temp):
        """Set target temperature for a zone.

        Create a quick veto with the specified temperature. If there is a
        quick mode that impact zone running on, remove it.
        """
        touch_quick_mode = False
        if self.system.quick_mode is not None and \
                self.system.quick_mode.for_zone:
            self.manager.remove_quick_mode()
            touch_quick_mode = True
            self.system.quick_mode = None

        self.set_zone_target_high_temperature(entity, zone, target_temp)

        if touch_quick_mode:
            self.refresh_listening_entities()

    def set_zone_target_high_temperature(self, entity, zone, temperature):
        """Set high target temperature for a zone., create a quick veto."""
        from pymultimatic.model import QuickVeto

        veto = QuickVeto(None, temperature)
        self.manager.set_zone_quick_veto(zone.id, veto)
        self.system.set_zone(zone.id, self.manager.get_zone(zone.id))
        entity.async_schedule_update_ha_state(True)

    def set_zone_target_low_temperature(self, entity, zone, temperature):
        """Set low temperature for a zone."""
        self.manager.set_zone_setback_temperature(zone.id, temperature)
        self.system.set_zone(zone.id, self.manager.get_zone(zone.id))
        entity.async_schedule_update_ha_state(True)

    def set_hot_water_operating_mode(self, entity, hot_water, mode):
        """Set hot water operation mode."""
        touch_quick_mode = False
        if self.system.quick_mode is not None and \
                self.system.quick_mode.for_dhw:
            self.manager.remove_quick_mode()
            touch_quick_mode = True
            self.system.quick_mode = None

        self.manager.set_hot_water_operating_mode(hot_water.id, mode)

        if touch_quick_mode:
            self.refresh_listening_entities()
        else:
            self.system.hot_water = self.manager.get_hot_water(hot_water.id)
            entity.async_schedule_update_ha_state(True)

    def set_room_operating_mode(self, entity, room, mode):
        """Set room operation mode.

        If there is a quick mode that impact room
        running on, remove it.
        """
        touch_quick_mode = False
        if self.system.quick_mode is not None and \
                self.system.quick_mode.for_room:
            self.manager.remove_quick_mode()
            touch_quick_mode = True
            self.system.quick_mode = None

        if room.quick_veto is not None:
            self.manager.remove_room_quick_veto(room.id)

        self.manager.set_room_operating_mode(room.id, mode)

        if touch_quick_mode:
            self.refresh_listening_entities()
        else:
            self.system.set_room(room.id, self.manager.get_room(room.id))
            entity.async_schedule_update_ha_state(True)

    def set_zone_operating_mode(self, entity, zone, mode):
        """Set zone operation mode.

        If there is a quick mode that impact room
        running on, remove it.
        """
        touch_quick_mode = False
        if self.system.quick_mode is not None and \
                self.system.quick_mode.for_zone:
            self.manager.remove_quick_mode()
            touch_quick_mode = True
            self.system.quick_mode = None

        if zone.quick_veto is not None:
            self.manager.remove_zone_quick_veto(zone.id)

        self.manager.set_zone_operating_mode(zone.id, mode)

        if touch_quick_mode:
            self.refresh_listening_entities()
        else:
            self.system.set_zone(zone.id, self.manager.get_zone(zone.id))
            entity.async_schedule_update_ha_state(True)


class VaillantServiceHandler:
    """Service implementation"""

    def __init__(self, hub) -> None:
        """Init."""
        self._hub = hub

    async def remove_quick_mode(self):
        """Remove quick mode. It has an impact on all components."""
        self._hub.manager.remove_quick_mode()
        self._hub.refresh_listening_entities()

    async def set_holiday_mode(self, start_date, end_date, temperature):
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        self._hub.manager.set_holiday_mode(start, end, temperature)
        self._hub.refresh_listening_entities()

    async def remove_holiday_mode(self):
        self._hub.manager.remove_holiday_mode()
        self._hub.refresh_listening_entities()

    async def set_quick_mode(self, quick_mode):
        """Set quick mode, it may impact the whole system."""
        from pymultimatic.model import QuickModes

        _LOGGER.debug('Will set quick mode %s', quick_mode)
        self._hub.manager.remove_quick_mode()
        self._hub.manager.set_quick_mode(QuickModes.get(quick_mode))
        self._hub.refresh_listening_entities()

    async def async_handle(self, service):
        """Dispatch a service call."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = service.data.copy()
        await getattr(self, method["method"])(**params)


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
