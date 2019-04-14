"""Support for Ness D8X/D16X devices."""
import datetime
import logging
from collections import namedtuple

import voluptuous as vol

from homeassistant.components.binary_sensor import DEVICE_CLASSES
from homeassistant.const import (ATTR_CODE, ATTR_STATE,
                                 EVENT_HOMEASSISTANT_STOP,
                                 CONF_SCAN_INTERVAL, CONF_HOST)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'ness_alarm'
DATA_NESS = 'ness_alarm'

CONF_DEVICE_PORT = 'port'
CONF_INFER_ARMING_STATE = 'infer_arming_state'
CONF_ZONES = 'zones'
CONF_ZONE_NAME = 'name'
CONF_ZONE_TYPE = 'type'
CONF_ZONE_ID = 'id'
ATTR_OUTPUT_ID = 'output_id'
DEFAULT_ZONES = []
DEFAULT_SCAN_INTERVAL = datetime.timedelta(minutes=1)
DEFAULT_INFER_ARMING_STATE = False

SIGNAL_ZONE_CHANGED = 'ness_alarm.zone_changed'
SIGNAL_ARMING_STATE_CHANGED = 'ness_alarm.arming_state_changed'

ZoneChangedData = namedtuple('ZoneChangedData', ['zone_id', 'state'])

DEFAULT_ZONE_TYPE = 'motion'
ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONE_NAME): cv.string,
    vol.Required(CONF_ZONE_ID): cv.positive_int,
    vol.Optional(CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE):
        vol.In(DEVICE_CLASSES)})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_DEVICE_PORT): cv.port,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
            vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_ZONES, default=DEFAULT_ZONES):
            vol.All(cv.ensure_list, [ZONE_SCHEMA]),
        vol.Optional(CONF_INFER_ARMING_STATE,
                     default=DEFAULT_INFER_ARMING_STATE):
            cv.boolean
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_PANIC = 'panic'
SERVICE_AUX = 'aux'

SERVICE_SCHEMA_PANIC = vol.Schema({
    vol.Required(ATTR_CODE): cv.string,
})
SERVICE_SCHEMA_AUX = vol.Schema({
    vol.Required(ATTR_OUTPUT_ID): cv.positive_int,
    vol.Optional(ATTR_STATE, default=True): cv.boolean,
})


async def async_setup(hass, config):
    """Set up the Ness Alarm platform."""
    from nessclient import Client, ArmingState
    conf = config[DOMAIN]

    zones = conf[CONF_ZONES]
    host = conf[CONF_HOST]
    port = conf[CONF_DEVICE_PORT]
    scan_interval = conf[CONF_SCAN_INTERVAL]
    infer_arming_state = conf[CONF_INFER_ARMING_STATE]

    client = Client(host=host, port=port, loop=hass.loop,
                    update_interval=scan_interval.total_seconds(),
                    infer_arming_state=infer_arming_state)
    hass.data[DATA_NESS] = client

    async def _close(event):
        await client.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close)

    hass.async_create_task(
        async_load_platform(hass, 'binary_sensor', DOMAIN, {CONF_ZONES: zones},
                            config))
    hass.async_create_task(
        async_load_platform(hass, 'alarm_control_panel', DOMAIN, {}, config))

    def on_zone_change(zone_id: int, state: bool):
        """Receives and propagates zone state updates."""
        async_dispatcher_send(hass, SIGNAL_ZONE_CHANGED, ZoneChangedData(
            zone_id=zone_id,
            state=state,
        ))

    def on_state_change(arming_state: ArmingState):
        """Receives and propagates arming state updates."""
        async_dispatcher_send(hass, SIGNAL_ARMING_STATE_CHANGED, arming_state)

    client.on_zone_change(on_zone_change)
    client.on_state_change(on_state_change)

    # Force update for current arming status and current zone states
    hass.loop.create_task(client.keepalive())
    hass.loop.create_task(client.update())

    async def handle_panic(call):
        await client.panic(call.data[ATTR_CODE])

    async def handle_aux(call):
        await client.aux(call.data[ATTR_OUTPUT_ID], call.data[ATTR_STATE])

    hass.services.async_register(DOMAIN, SERVICE_PANIC, handle_panic,
                                 schema=SERVICE_SCHEMA_PANIC)
    hass.services.async_register(DOMAIN, SERVICE_AUX, handle_aux,
                                 schema=SERVICE_SCHEMA_AUX)

    return True
