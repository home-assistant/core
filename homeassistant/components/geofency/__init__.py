"""
Support for Geofency.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/geofency/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import HTTP_UNPROCESSABLE_ENTITY, STATE_NOT_HOME, \
    ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'geofency'
DEPENDENCIES = ['http']

CONF_MOBILE_BEACONS = 'mobile_beacons'

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Optional(CONF_MOBILE_BEACONS, default=[]): vol.All(
            cv.ensure_list,
            [cv.string]
        ),
    }),
}, extra=vol.ALLOW_EXTRA)

ATTR_CURRENT_LATITUDE = 'currentLatitude'
ATTR_CURRENT_LONGITUDE = 'currentLongitude'

BEACON_DEV_PREFIX = 'beacon'

LOCATION_ENTRY = '1'
LOCATION_EXIT = '0'

URL = '/api/geofency'

TRACKER_UPDATE = '{}_tracker_update'.format(DOMAIN)


async def async_setup(hass, hass_config):
    """Set up the Geofency component."""
    config = hass_config[DOMAIN]
    mobile_beacons = config[CONF_MOBILE_BEACONS]
    hass.data[DOMAIN] = [slugify(beacon) for beacon in mobile_beacons]
    hass.http.register_view(GeofencyView(hass.data[DOMAIN]))

    hass.async_create_task(
        async_load_platform(hass, 'device_tracker', DOMAIN, {}, hass_config)
    )
    return True


class GeofencyView(HomeAssistantView):
    """View to handle Geofency requests."""

    url = URL
    name = 'api:geofency'

    def __init__(self, mobile_beacons):
        """Initialize Geofency url endpoints."""
        self.mobile_beacons = mobile_beacons

    async def post(self, request):
        """Handle Geofency requests."""
        data = await request.post()
        hass = request.app['hass']

        data = self._validate_data(data)
        if not data:
            return "Invalid data", HTTP_UNPROCESSABLE_ENTITY

        if self._is_mobile_beacon(data):
            return await self._set_location(hass, data, None)
        if data['entry'] == LOCATION_ENTRY:
            location_name = data['name']
        else:
            location_name = STATE_NOT_HOME
            if ATTR_CURRENT_LATITUDE in data:
                data[ATTR_LATITUDE] = data[ATTR_CURRENT_LATITUDE]
                data[ATTR_LONGITUDE] = data[ATTR_CURRENT_LONGITUDE]

        return await self._set_location(hass, data, location_name)

    @staticmethod
    def _validate_data(data):
        """Validate POST payload."""
        data = data.copy()

        required_attributes = ['address', 'device', 'entry',
                               'latitude', 'longitude', 'name']

        valid = True
        for attribute in required_attributes:
            if attribute not in data:
                valid = False
                _LOGGER.error("'%s' not specified in message", attribute)

        if not valid:
            return {}

        data['address'] = data['address'].replace('\n', ' ')
        data['device'] = slugify(data['device'])
        data['name'] = slugify(data['name'])

        gps_attributes = [ATTR_LATITUDE, ATTR_LONGITUDE,
                          ATTR_CURRENT_LATITUDE, ATTR_CURRENT_LONGITUDE]

        for attribute in gps_attributes:
            if attribute in data:
                data[attribute] = float(data[attribute])

        return data

    def _is_mobile_beacon(self, data):
        """Check if we have a mobile beacon."""
        return 'beaconUUID' in data and data['name'] in self.mobile_beacons

    @staticmethod
    def _device_name(data):
        """Return name of device tracker."""
        if 'beaconUUID' in data:
            return "{}_{}".format(BEACON_DEV_PREFIX, data['name'])
        return data['device']

    async def _set_location(self, hass, data, location_name):
        """Fire HA event to set location."""
        device = self._device_name(data)

        async_dispatcher_send(
            hass,
            TRACKER_UPDATE,
            device,
            (data[ATTR_LATITUDE], data[ATTR_LONGITUDE]),
            location_name,
            data
        )

        return "Setting location for {}".format(device)
