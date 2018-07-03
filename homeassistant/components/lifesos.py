"""
Support for LifeSOS devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/lifesos/
"""
import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_NAME, CONF_SWITCHES, CONF_ID,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['lifesospy==0.7.0']

_LOGGER = logging.getLogger(__name__)

ATTR_ALARM_ENTITY_ID = 'alarm_entity_id'
ATTR_DEVICE_ENTITY_ID = 'device_entity_id'
ATTR_RSSI_BARS = 'rssi_bars'
ATTR_RSSI_DB = 'rssi_db'
ATTR_ZONE = 'zone'

CONF_TRIGGER_DURATION = 'trigger_duration'

DATA_ALARM = 'lifesos_alarm'
DATA_BASEUNIT = 'lifesos_baseunit'
DATA_DEVICES = 'lifesos_devices'

DEFAULT_NAME = 'LifeSOS'
DEFAULT_PASSWORD = ''
DEFAULT_PORT = 1680
DEFAULT_SWITCHES = None
DEFAULT_TRIGGER_DURATION = 5

DOMAIN = 'lifesos'

EVENT_BASEUNIT = 'lifesos_baseunit'

SIGNAL_EVENT = '{}.event'.format(DOMAIN)
SIGNAL_PROPERTIES_CHANGED = '{}.properties_changed'.format(DOMAIN)
SIGNAL_SWITCH_STATE_CHANGED = '{}.switch_state_changed'.format(DOMAIN)

SERVICE_SYNC_DATETIME = 'sync_datetime'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SWITCHES, default=DEFAULT_SWITCHES):
            vol.All(cv.ensure_list_csv, [cv.positive_int]),
        vol.Optional(CONF_TRIGGER_DURATION, default=DEFAULT_TRIGGER_DURATION):
            cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up for LifeSOS devices."""
    from lifesospy.baseunit import BaseUnit

    conf = config.get(DOMAIN)

    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    password = conf.get(CONF_PASSWORD)
    name = conf.get(CONF_NAME)
    switches = conf.get(CONF_SWITCHES)

    baseunit = BaseUnit(host, port)
    baseunit.password = password

    hass.data[DATA_BASEUNIT] = baseunit
    hass.data[DATA_DEVICES] = {}

    @callback
    def _start_lifesos(event):
        baseunit.start()

        # Capture shutdown so we can close connection
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_lifesos)

    @callback
    def _stop_lifesos(event):
        baseunit.stop()

    @callback
    def _on_device_added(baseunit, device):
        # When a device is added to base unit, create an entity for it
        if device.device_id not in hass.data[DATA_DEVICES]:
            hass.async_add_job(
                async_setup_device, hass, config, name, device)

    @callback
    def _on_device_deleted(baseunit, device):
        # When a device is deleted from base unit, remove the entity
        device_entity = hass.data[DATA_DEVICES].pop(device.device_id, None)
        if device_entity is not None:
            hass.states.async_remove(device_entity.entity_id)

    @callback
    def _on_event(baseunit, contact_id):
        # Signal base unit events for the alarm panel platform
        async_dispatcher_send(hass, SIGNAL_EVENT, contact_id)

        # Make the base unit event available for automation, as it provides
        # more info than just the simple 'triggered' state from alarm panel;
        # eg. type of alert (burglar, fire, medical, etc), zone that raised
        # an alert, as well as warnings like power or RF loss/restoration.
        from lifesospy.enums import ContactIDEventCode as EventCode
        if contact_id.event_code not in {EventCode.PeriodicTestReport}:
            event_data = contact_id.as_dict()
            # Include alarm and device entity id when available
            alarm_entity = hass.data[DATA_ALARM]
            if alarm_entity:
                event_data[ATTR_ALARM_ENTITY_ID] = alarm_entity.entity_id
            if contact_id.zone:
                # When event contains device detail, include entity id
                device_entity = next(
                    (de for de in hass.data[DATA_DEVICES].values() if
                     de.device_state_attributes[ATTR_ZONE] == contact_id.zone),
                    None)
                if device_entity:
                    event_data[ATTR_DEVICE_ENTITY_ID] = device_entity.entity_id
            hass.bus.async_fire(EVENT_BASEUNIT, event_data)

    @callback
    def _on_properties_changed(baseunit, changes):
        # Signal changes to base unit properties for our platforms
        async_dispatcher_send(hass, SIGNAL_PROPERTIES_CHANGED, changes)

    @callback
    def _on_switch_state_changed(baseunit, switch_number, state):
        # Signal switch state changes for the switch platform
        async_dispatcher_send(
            hass, SIGNAL_SWITCH_STATE_CHANGED, switch_number, state)

    async def async_sync_datetime(call):
        """Set remote date/time to the local date/time."""
        await baseunit.async_set_datetime()

    hass.services.async_register(
        DOMAIN, SERVICE_SYNC_DATETIME, async_sync_datetime)

    hass.async_add_job(
        async_load_platform(
            hass, 'alarm_control_panel', DOMAIN,
            {CONF_NAME: name},
            config))

    if switches:
        hass.async_add_job(
            async_load_platform(
                hass, 'switch', DOMAIN,
                {CONF_NAME: name,
                 CONF_SWITCHES: switches},
                config))

    # Assign all base unit callbacks; we will signal our platforms if needed
    baseunit.on_device_added = _on_device_added
    baseunit.on_device_deleted = _on_device_deleted
    baseunit.on_event = _on_event
    baseunit.on_properties_changed = _on_properties_changed
    baseunit.on_switch_state_changed = _on_switch_state_changed

    # Connect to base unit and get initial state when HA has started
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _start_lifesos)

    return True


async def async_setup_device(hass, config, name, device):
    """Set up a LifeSOS device."""
    from lifesospy.enums import DeviceType

    conf = config.get(DOMAIN)

    # Skip device if type was not recognised
    if device.type is None:
        _LOGGER.debug("Unrecognised device type 0x%02x}", device.type_value)
        return

    # Remote controllers and keypads don't really have a suitable type
    # to represent them in HA, and since automations can just use the alarm
    # panel state to achieve a similar result anyway, just ignore them.
    if device.type in [DeviceType.RemoteController, DeviceType.KeyPad,
                       DeviceType.XKeyPad]:
        pass

    # Device types to be represented as a Binary Sensor in HA
    elif device.type in [
            DeviceType.FloodDetector, DeviceType.FloodDetector2,
            DeviceType.MedicalButton, DeviceType.AnalogSensor,
            DeviceType.AnalogSensor2, DeviceType.SmokeDetector,
            DeviceType.PressureSensor, DeviceType.PressureSensor2,
            DeviceType.CODetector, DeviceType.CO2Sensor, DeviceType.CO2Sensor2,
            DeviceType.GasDetector, DeviceType.DoorMagnet,
            DeviceType.VibrationSensor, DeviceType.PIRSensor,
            DeviceType.GlassBreakDetector]:
        await async_load_platform(
            hass, 'binary_sensor', DOMAIN,
            {CONF_NAME: name,
             CONF_ID: device.device_id,
             CONF_TRIGGER_DURATION: conf.get(CONF_TRIGGER_DURATION)},
            config)

    # Device types to be represented as a Sensor in HA
    elif device.type in [
            DeviceType.HumidSensor, DeviceType.HumidSensor2,
            DeviceType.TempSensor, DeviceType.TempSensor2,
            DeviceType.LightSensor, DeviceType.LightDetector,
            DeviceType.ACCurrentMeter, DeviceType.ACCurrentMeter2,
            DeviceType.ThreePhaseACMeter]:

        await async_load_platform(
            hass, 'sensor', DOMAIN,
            {CONF_NAME: name,
             CONF_ID: device.device_id},
            config)

    # Any remaining device types are not supported at this time
    else:
        _LOGGER.debug("Unsupported device type '%s'", device.type.name)


class LifeSOSDevice(Entity):
    """Base class for all LifeSOS devices."""

    def __init__(self, baseunit, name):
        """Initialize the LifeSOS device."""
        self._baseunit = baseunit
        self._name = name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False


class LifeSOSBaseSensor(LifeSOSDevice):
    """Common base class for all LifeSOS enrolled sensors."""

    def __init__(self, baseunit, name, device):
        super().__init__(
            baseunit,
            "{0} {1} {2:06x}".format(
                name,
                device.type.name,
                device.device_id))

        self._device = device

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ZONE: self._device.zone,
            ATTR_RSSI_DB: self._device.rssi_db,
            ATTR_RSSI_BARS: self._device.rssi_bars,
        }

    @property
    def unique_id(self):
        """Return a unique ID."""

        # Device ID is assigned by the manufacturer to ensure each device
        # has a unique ID, so we can just use that
        return "{0:06x}".format(self._device.device_id)
