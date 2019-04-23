"""Support for Satel Integra devices."""
import logging

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

REQUIREMENTS = ['satel_integra==0.3.2']

DEFAULT_ALARM_NAME = 'satel_integra'
DEFAULT_PORT = 7094
DEFAULT_CONF_ARM_HOME_MODE = 1
DEFAULT_DEVICE_PARTITION = 1
DEFAULT_ZONE_TYPE = 'motion'

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'satel_integra'

DATA_SATEL = 'satel_integra'

CONF_DEVICE_PORT = 'port'
CONF_DEVICE_PARTITION = 'partition'
CONF_ARM_HOME_MODE = 'arm_home_mode'
CONF_ZONE_NAME = 'name'
CONF_ZONE_TYPE = 'type'
CONF_ZONES = 'zones'
CONF_OUTPUTS = 'outputs'

ZONES = 'zones'

SIGNAL_PANEL_MESSAGE = 'satel_integra.panel_message'
SIGNAL_PANEL_ARM_AWAY = 'satel_integra.panel_arm_away'
SIGNAL_PANEL_ARM_HOME = 'satel_integra.panel_arm_home'
SIGNAL_PANEL_DISARM = 'satel_integra.panel_disarm'

SIGNAL_ZONES_UPDATED = 'satel_integra.zones_updated'
SIGNAL_OUTPUTS_UPDATED = 'satel_integra.outputs_updated'

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONE_NAME): cv.string,
    vol.Optional(CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE): cv.string})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_DEVICE_PARTITION,
                     default=DEFAULT_DEVICE_PARTITION): cv.positive_int,
        vol.Optional(CONF_ARM_HOME_MODE,
                     default=DEFAULT_CONF_ARM_HOME_MODE): vol.In([1, 2, 3]),
        vol.Optional(CONF_ZONES,
                     default={}): {vol.Coerce(int): ZONE_SCHEMA},
        vol.Optional(CONF_OUTPUTS,
                     default={}): {vol.Coerce(int): ZONE_SCHEMA},
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Satel Integra component."""
    conf = config.get(DOMAIN)

    zones = conf.get(CONF_ZONES)
    outputs = conf.get(CONF_OUTPUTS)
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_DEVICE_PORT)
    partition = conf.get(CONF_DEVICE_PARTITION)

    from satel_integra.satel_integra import AsyncSatel

    controller = AsyncSatel(host, port, hass.loop, zones, outputs, partition)

    hass.data[DATA_SATEL] = controller

    result = await controller.connect()

    if not result:
        return False

    async def _close():
        controller.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close())

    _LOGGER.debug("Arm home config: %s, mode: %s ",
                  conf,
                  conf.get(CONF_ARM_HOME_MODE))

    hass.async_create_task(
        async_load_platform(hass, 'alarm_control_panel', DOMAIN, conf, config))

    hass.async_create_task(
        async_load_platform(hass, 'binary_sensor', DOMAIN,
                            {CONF_ZONES: zones, CONF_OUTPUTS: outputs}, config)
        )

    @callback
    def alarm_status_update_callback():
        """Send status update received from alarm to home assistant."""
        _LOGGER.debug("Sending request to update panel state")
        async_dispatcher_send(hass, SIGNAL_PANEL_MESSAGE)

    @callback
    def zones_update_callback(status):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Zones callback, status: %s", status)
        async_dispatcher_send(hass, SIGNAL_ZONES_UPDATED, status[ZONES])

    @callback
    def outputs_update_callback(status):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Outputs updated callback , status: %s", status)
        async_dispatcher_send(hass, SIGNAL_OUTPUTS_UPDATED, status["outputs"])

    # Create a task instead of adding a tracking job, since this task will
    # run until the connection to satel_integra is closed.
    hass.loop.create_task(controller.keep_alive())
    hass.loop.create_task(
        controller.monitor_status(
            alarm_status_update_callback,
            zones_update_callback,
            outputs_update_callback)
    )

    return True
