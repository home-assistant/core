"""
Support for Vanderbilt (formerly Siemens) SPC alarm systems.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/spc/
"""
import asyncio
import json
import logging
from urllib.parse import urljoin

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED, STATE_OFF, STATE_ON, STATE_UNAVAILABLE,
    STATE_UNKNOWN)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['websockets==3.2']

_LOGGER = logging.getLogger(__name__)

ATTR_DISCOVER_DEVICES = 'devices'
ATTR_DISCOVER_AREAS = 'areas'

CONF_WS_URL = 'ws_url'
CONF_API_URL = 'api_url'

DATA_REGISTRY = 'spc_registry'
DATA_API = 'spc_api'
DOMAIN = 'spc'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_WS_URL): cv.string,
        vol.Required(CONF_API_URL): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the SPC platform."""
    hass.data[DATA_REGISTRY] = SpcRegistry()

    api = SpcWebGateway(hass,
                        config[DOMAIN].get(CONF_API_URL),
                        config[DOMAIN].get(CONF_WS_URL))

    hass.data[DATA_API] = api

    # add sensor devices for each zone (typically motion/fire/door sensors)
    zones = yield from api.get_zones()
    if zones:
        hass.async_create_task(discovery.async_load_platform(
            hass, 'binary_sensor', DOMAIN,
            {ATTR_DISCOVER_DEVICES: zones}, config))

    # create a separate alarm panel for each area
    areas = yield from api.get_areas()
    if areas:
        hass.async_create_task(discovery.async_load_platform(
            hass, 'alarm_control_panel', DOMAIN,
            {ATTR_DISCOVER_AREAS: areas}, config))

    # start listening for incoming events over websocket
    api.start_listener(_async_process_message, hass.data[DATA_REGISTRY])

    return True


@asyncio.coroutine
def _async_process_message(sia_message, spc_registry):
    spc_id = sia_message['sia_address']
    sia_code = sia_message['sia_code']

    # BA - Burglary Alarm
    # CG - Close Area
    # NL - Perimeter Armed
    # OG - Open Area
    # ZO - Zone Open
    # ZC - Zone Close
    # ZX - Zone Short
    # ZD - Zone Disconnected

    extra = {}

    if sia_code in ('BA', 'CG', 'NL', 'OG'):
        # change in area status, notify alarm panel device
        device = spc_registry.get_alarm_device(spc_id)
        data = sia_message['description'].split('¦')
        if len(data) == 3:
            extra['changed_by'] = data[1]
    else:
        # Change in zone status, notify sensor device
        device = spc_registry.get_sensor_device(spc_id)

    sia_code_to_state_map = {
        'BA': STATE_ALARM_TRIGGERED,
        'CG': STATE_ALARM_ARMED_AWAY,
        'NL': STATE_ALARM_ARMED_HOME,
        'OG': STATE_ALARM_DISARMED,
        'ZO': STATE_ON,
        'ZC': STATE_OFF,
        'ZX': STATE_UNKNOWN,
        'ZD': STATE_UNAVAILABLE,
    }

    new_state = sia_code_to_state_map.get(sia_code, None)

    if new_state and not device:
        _LOGGER.warning(
            "No device mapping found for SPC area/zone id %s", spc_id)
    elif new_state:
        yield from device.async_update_from_spc(new_state, extra)


class SpcRegistry:
    """Maintain mappings between SPC zones/areas and HA entities."""

    def __init__(self):
        """Initialize the registry."""
        self._zone_id_to_sensor_map = {}
        self._area_id_to_alarm_map = {}

    def register_sensor_device(self, zone_id, device):
        """Add a sensor device to the registry."""
        self._zone_id_to_sensor_map[zone_id] = device

    def get_sensor_device(self, zone_id):
        """Retrieve a sensor device for a specific zone."""
        return self._zone_id_to_sensor_map.get(zone_id, None)

    def register_alarm_device(self, area_id, device):
        """Add an alarm device to the registry."""
        self._area_id_to_alarm_map[area_id] = device

    def get_alarm_device(self, area_id):
        """Retrieve an alarm device for a specific area."""
        return self._area_id_to_alarm_map.get(area_id, None)


@asyncio.coroutine
def _ws_process_message(message, async_callback, *args):
    if message.get('status', '') != 'success':
        _LOGGER.warning(
            "Unsuccessful websocket message delivered, ignoring: %s", message)
    try:
        yield from async_callback(message['data']['sia'], *args)
    except:  # noqa: E722 pylint: disable=bare-except
        _LOGGER.exception("Exception in callback, ignoring")


class SpcWebGateway:
    """Simple binding for the Lundix SPC Web Gateway REST API."""

    AREA_COMMAND_SET = 'set'
    AREA_COMMAND_PART_SET = 'set_a'
    AREA_COMMAND_UNSET = 'unset'

    def __init__(self, hass, api_url, ws_url):
        """Initialize the web gateway client."""
        self._hass = hass
        self._api_url = api_url
        self._ws_url = ws_url
        self._ws = None

    @asyncio.coroutine
    def get_zones(self):
        """Retrieve all available zones."""
        return (yield from self._get_data('zone'))

    @asyncio.coroutine
    def get_areas(self):
        """Retrieve all available areas."""
        return (yield from self._get_data('area'))

    @asyncio.coroutine
    def send_area_command(self, area_id, command):
        """Send an area command."""
        _LOGGER.debug(
            "Sending SPC area command '%s' to area %s", command, area_id)
        resource = "area/{}/{}".format(area_id, command)
        return (yield from self._call_web_gateway(resource, use_get=False))

    def start_listener(self, async_callback, *args):
        """Start the websocket listener."""
        asyncio.ensure_future(self._ws_listen(async_callback, *args))

    def _build_url(self, resource):
        return urljoin(self._api_url, "spc/{}".format(resource))

    @asyncio.coroutine
    def _get_data(self, resource):
        """Get the data from the resource."""
        data = yield from self._call_web_gateway(resource)
        if not data:
            return False
        if data['status'] != 'success':
            _LOGGER.error(
                "SPC Web Gateway call unsuccessful for resource: %s", resource)
            return False
        return [item for item in data['data'][resource]]

    @asyncio.coroutine
    def _call_web_gateway(self, resource, use_get=True):
        """Call web gateway for data."""
        response = None
        session = None
        url = self._build_url(resource)
        try:
            _LOGGER.debug("Attempting to retrieve SPC data from %s", url)
            session = \
                self._hass.helpers.aiohttp_client.async_get_clientsession()
            with async_timeout.timeout(10, loop=self._hass.loop):
                action = session.get if use_get else session.put
                response = yield from action(url)
            if response.status != 200:
                _LOGGER.error(
                    "SPC Web Gateway returned http status %d, response %s",
                    response.status, (yield from response.text()))
                return False
            result = yield from response.json()
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting SPC data from %s", url)
            return False
        except aiohttp.ClientError:
            _LOGGER.exception("Error getting SPC data from %s", url)
            return False
        finally:
            if session:
                yield from session.close()
            if response:
                yield from response.release()
        _LOGGER.debug("Data from SPC: %s", result)
        return result

    @asyncio.coroutine
    def _ws_read(self):
        """Read from websocket."""
        import websockets as wslib

        try:
            if not self._ws:
                self._ws = yield from wslib.connect(self._ws_url)
                _LOGGER.info("Connected to websocket at %s", self._ws_url)
        except Exception as ws_exc:    # pylint: disable=broad-except
            _LOGGER.error("Failed to connect to websocket: %s", ws_exc)
            return

        result = None

        try:
            result = yield from self._ws.recv()
            _LOGGER.debug("Data from websocket: %s", result)
        except Exception as ws_exc:    # pylint: disable=broad-except
            _LOGGER.error("Failed to read from websocket: %s", ws_exc)
            try:
                yield from self._ws.close()
            finally:
                self._ws = None

        return result

    @asyncio.coroutine
    def _ws_listen(self, async_callback, *args):
        """Listen on websocket."""
        try:
            while True:
                result = yield from self._ws_read()

                if result:
                    yield from _ws_process_message(
                        json.loads(result), async_callback, *args)
                else:
                    _LOGGER.info("Trying again in 30 seconds")
                    yield from asyncio.sleep(30)

        finally:
            if self._ws:
                yield from self._ws.close()
