"""
This component provides basic support for Abode Home Security system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/abode/
"""
import asyncio
import logging
from functools import partial
from os import path

import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (ATTR_ATTRIBUTION, ATTR_DATE, ATTR_TIME,
                                 ATTR_ENTITY_ID, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_EXCLUDE, CONF_NAME,
                                 EVENT_HOMEASSISTANT_STOP,
                                 EVENT_HOMEASSISTANT_START)

REQUIREMENTS = ['abodepy==0.12.1']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by goabode.com"
CONF_LIGHTS = "lights"
CONF_POLLING = "polling"

DOMAIN = 'abode'

NOTIFICATION_ID = 'abode_notification'
NOTIFICATION_TITLE = 'Abode Security Setup'

EVENT_ABODE_ALARM = 'abode_alarm'
EVENT_ABODE_ALARM_END = 'abode_alarm_end'
EVENT_ABODE_AUTOMATION = 'abode_automation'
EVENT_ABODE_FAULT = 'abode_panel_fault'
EVENT_ABODE_RESTORE = 'abode_panel_restore'

SERVICE_SETTINGS = 'change_setting'
SERVICE_CAPTURE_IMAGE = 'capture_image'
SERVICE_TRIGGER = 'trigger_quick_action'

ATTR_DEVICE_ID = 'device_id'
ATTR_DEVICE_NAME = 'device_name'
ATTR_DEVICE_TYPE = 'device_type'
ATTR_EVENT_CODE = 'event_code'
ATTR_EVENT_NAME = 'event_name'
ATTR_EVENT_TYPE = 'event_type'
ATTR_EVENT_UTC = 'event_utc'
ATTR_SETTING = 'setting'
ATTR_USER_NAME = 'user_name'
ATTR_VALUE = 'value'

ABODE_DEVICE_ID_LIST_SCHEMA = vol.Schema([str])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_POLLING, default=False): cv.boolean,
        vol.Optional(CONF_EXCLUDE, default=[]): ABODE_DEVICE_ID_LIST_SCHEMA,
        vol.Optional(CONF_LIGHTS, default=[]): ABODE_DEVICE_ID_LIST_SCHEMA
    }),
}, extra=vol.ALLOW_EXTRA)

CHANGE_SETTING_SCHEMA = vol.Schema({
    vol.Required(ATTR_SETTING): cv.string,
    vol.Required(ATTR_VALUE): cv.string
})

CAPTURE_IMAGE_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
})

TRIGGER_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
})

ABODE_PLATFORMS = [
    'alarm_control_panel', 'binary_sensor', 'lock', 'switch', 'cover',
    'camera', 'light'
]


class AbodeSystem(object):
    """Abode System class."""

    def __init__(self, username, password, name, polling, exclude, lights):
        """Initialize the system."""
        import abodepy
        self.abode = abodepy.Abode(username, password,
                                   auto_login=True,
                                   get_devices=True,
                                   get_automations=True)
        self.name = name
        self.polling = polling
        self.exclude = exclude
        self.lights = lights
        self.devices = []

    def is_excluded(self, device):
        """Check if a device is configured to be excluded."""
        return device.device_id in self.exclude

    def is_automation_excluded(self, automation):
        """Check if an automation is configured to be excluded."""
        return automation.automation_id in self.exclude

    def is_light(self, device):
        """Check if a switch device is configured as a light."""
        import abodepy.helpers.constants as CONST

        return (device.generic_type == CONST.TYPE_LIGHT or
                (device.generic_type == CONST.TYPE_SWITCH and
                 device.device_id in self.lights))


def setup(hass, config):
    """Set up Abode component."""
    from abodepy.exceptions import AbodeException

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    name = conf.get(CONF_NAME)
    polling = conf.get(CONF_POLLING)
    exclude = conf.get(CONF_EXCLUDE)
    lights = conf.get(CONF_LIGHTS)

    try:
        hass.data[DOMAIN] = AbodeSystem(
            username, password, name, polling, exclude, lights)
    except (AbodeException, ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Abode: %s", str(ex))

        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    setup_hass_services(hass)
    setup_hass_events(hass)
    setup_abode_events(hass)

    for platform in ABODE_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True


def setup_hass_services(hass):
    """Home assistant services."""
    from abodepy.exceptions import AbodeException

    def change_setting(call):
        """Change an Abode system setting."""
        setting = call.data.get(ATTR_SETTING)
        value = call.data.get(ATTR_VALUE)

        try:
            hass.data[DOMAIN].abode.set_setting(setting, value)
        except AbodeException as ex:
            _LOGGER.warning(ex)

    def capture_image(call):
        """Capture a new image."""
        entity_ids = call.data.get(ATTR_ENTITY_ID)

        target_devices = [device for device in hass.data[DOMAIN].devices
                          if device.entity_id in entity_ids]

        for device in target_devices:
            device.capture()

    def trigger_quick_action(call):
        """Trigger a quick action."""
        entity_ids = call.data.get(ATTR_ENTITY_ID, None)

        target_devices = [device for device in hass.data[DOMAIN].devices
                          if device.entity_id in entity_ids]

        for device in target_devices:
            device.trigger()

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))[DOMAIN]

    hass.services.register(
        DOMAIN, SERVICE_SETTINGS, change_setting,
        descriptions.get(SERVICE_SETTINGS),
        schema=CHANGE_SETTING_SCHEMA)

    hass.services.register(
        DOMAIN, SERVICE_CAPTURE_IMAGE, capture_image,
        descriptions.get(SERVICE_CAPTURE_IMAGE),
        schema=CAPTURE_IMAGE_SCHEMA)

    hass.services.register(
        DOMAIN, SERVICE_TRIGGER, trigger_quick_action,
        descriptions.get(SERVICE_TRIGGER),
        schema=TRIGGER_SCHEMA)


def setup_hass_events(hass):
    """Home assistant start and stop callbacks."""
    def startup(event):
        """Listen for push events."""
        hass.data[DOMAIN].abode.events.start()

    def logout(event):
        """Logout of Abode."""
        if not hass.data[DOMAIN].polling:
            hass.data[DOMAIN].abode.events.stop()

        hass.data[DOMAIN].abode.logout()
        _LOGGER.info("Logged out of Abode")

    if not hass.data[DOMAIN].polling:
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, startup)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, logout)


def setup_abode_events(hass):
    """Event callbacks."""
    import abodepy.helpers.timeline as TIMELINE

    def event_callback(event, event_json):
        """Handle an event callback from Abode."""
        data = {
            ATTR_DEVICE_ID: event_json.get(ATTR_DEVICE_ID, ''),
            ATTR_DEVICE_NAME: event_json.get(ATTR_DEVICE_NAME, ''),
            ATTR_DEVICE_TYPE: event_json.get(ATTR_DEVICE_TYPE, ''),
            ATTR_EVENT_CODE: event_json.get(ATTR_EVENT_CODE, ''),
            ATTR_EVENT_NAME: event_json.get(ATTR_EVENT_NAME, ''),
            ATTR_EVENT_TYPE: event_json.get(ATTR_EVENT_TYPE, ''),
            ATTR_EVENT_UTC: event_json.get(ATTR_EVENT_UTC, ''),
            ATTR_USER_NAME: event_json.get(ATTR_USER_NAME, ''),
            ATTR_DATE: event_json.get(ATTR_DATE, ''),
            ATTR_TIME: event_json.get(ATTR_TIME, ''),
        }

        hass.bus.fire(event, data)

    events = [TIMELINE.ALARM_GROUP, TIMELINE.ALARM_END_GROUP,
              TIMELINE.PANEL_FAULT_GROUP, TIMELINE.PANEL_RESTORE_GROUP,
              TIMELINE.AUTOMATION_GROUP]

    for event in events:
        hass.data[DOMAIN].abode.events.add_event_callback(
            event,
            partial(event_callback, event))


class AbodeDevice(Entity):
    """Representation of an Abode device."""

    def __init__(self, data, device):
        """Initialize a sensor for Abode device."""
        self._data = data
        self._device = device

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe Abode events."""
        self.hass.async_add_job(
            self._data.abode.events.add_device_callback,
            self._device.device_id, self._update_callback
        )

    @property
    def should_poll(self):
        """Return the polling state."""
        return self._data.polling

    def update(self):
        """Update automation state."""
        self._device.refresh()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._device.name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'device_id': self._device.device_id,
            'battery_low': self._device.battery_low,
            'no_response': self._device.no_response,
            'device_type': self._device.type
        }

    def _update_callback(self, device):
        """Update the device state."""
        self.schedule_update_ha_state()


class AbodeAutomation(Entity):
    """Representation of an Abode automation."""

    def __init__(self, data, automation, event=None):
        """Initialize for Abode automation."""
        self._data = data
        self._automation = automation
        self._event = event

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe Abode events."""
        if self._event:
            self.hass.async_add_job(
                self._data.abode.events.add_event_callback,
                self._event, self._update_callback
            )

    @property
    def should_poll(self):
        """Return the polling state."""
        return self._data.polling

    def update(self):
        """Update automation state."""
        self._automation.refresh()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._automation.name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'automation_id': self._automation.automation_id,
            'type': self._automation.type,
            'sub_type': self._automation.sub_type
        }

    def _update_callback(self, device):
        """Update the device state."""
        self._automation.refresh()
        self.schedule_update_ha_state()
