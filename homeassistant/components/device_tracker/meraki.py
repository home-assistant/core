"""
Support for the Meraki CMX location service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.meraki/

"""
import asyncio
import logging
import json

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (HTTP_BAD_REQUEST, HTTP_UNPROCESSABLE_ENTITY)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, SOURCE_TYPE_ROUTER)

CONF_VALIDATOR = 'validator'
CONF_SECRET = 'secret'
DEPENDENCIES = ['http']
URL = '/api/meraki'
VERSION = '2.0'


_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_VALIDATOR): cv.string,
    vol.Required(CONF_SECRET): cv.string
})


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up an endpoint for the Meraki tracker."""
    hass.http.register_view(
        MerakiView(config, async_see))

    return True


class MerakiView(HomeAssistantView):
    """View to handle Meraki requests."""

    url = URL
    name = 'api:meraki'

    def __init__(self, config, async_see):
        """Initialize Meraki URL endpoints."""
        self.async_see = async_see
        self.validator = config[CONF_VALIDATOR]
        self.secret = config[CONF_SECRET]

    @asyncio.coroutine
    def get(self, request):
        """Meraki message received as GET."""
        return self.validator

    @asyncio.coroutine
    def post(self, request):
        """Meraki CMX message received."""
        try:
            data = yield from request.json()
        except ValueError:
            return self.json_message('Invalid JSON', HTTP_BAD_REQUEST)
        _LOGGER.debug("Meraki Data from Post: %s", json.dumps(data))
        if not data.get('secret', False):
            _LOGGER.error("secret invalid")
            return self.json_message('No secret', HTTP_UNPROCESSABLE_ENTITY)
        if data['secret'] != self.secret:
            _LOGGER.error("Invalid Secret received from Meraki")
            return self.json_message('Invalid secret',
                                     HTTP_UNPROCESSABLE_ENTITY)
        elif data['version'] != VERSION:
            _LOGGER.error("Invalid API version: %s", data['version'])
            return self.json_message('Invalid version',
                                     HTTP_UNPROCESSABLE_ENTITY)
        else:
            _LOGGER.debug('Valid Secret')
            if data['type'] == "DevicesSeen":
                _LOGGER.debug("WiFi Devices Seen")
            elif data['type'] == "BluetoothDevicesSeen":
                _LOGGER.debug("Bluetooth Devices Seen")
            else:
                _LOGGER.error("Unknown Device %s", type)
                return self.json_message('invalid device type',
                                         HTTP_UNPROCESSABLE_ENTITY)
        if len(data["data"]["observations"]) == 0:
            _LOGGER.debug("No observations found")
            return
        res = yield from self._handle(request.app['hass'], data)
        return res

    @asyncio.coroutine
    def _handle(self, hass, data):
        for i in data["data"]["observations"]:
            data["data"]["secret"] = "hidden"
            lat = i["location"]["lat"]
            lng = i["location"]["lng"]
            accuracy = int(float(i["location"]["unc"]))
            mac = i["clientMac"]
            _LOGGER.debug("clientMac: %s", mac)
            gps_location = (lat, lng)
            attrs = {}
            if i.get('os', False):
                attrs['os'] = i['os']
            if i.get('manufacturer', False):
                attrs['manufacturer'] = i['manufacturer']
            if i.get('ipv4', False):
                attrs['ipv4'] = i['ipv4']
            if i.get('ipv6', False):
                attrs['ipv6'] = i['ipv6']
            if i.get('seenTime', False):
                attrs['seenTime'] = i['seenTime']
            if i.get('ssid', False):
                attrs['ssid'] = i['ssid']
            yield from self.async_see(
                gps=gps_location,
                mac=mac,
                source_type=SOURCE_TYPE_ROUTER,
                gps_accuracy=accuracy,
                attributes=attrs
            )
