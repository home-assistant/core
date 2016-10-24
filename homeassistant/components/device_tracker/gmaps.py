"""
Get location from Google Maps Geolocation API

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.gmaps/
"""
import logging
import voluptuous as vol

from homeassistant.const import (CONF_API_KEY, CONF_ID,
                                 CONF_ACCURACY, CONF_SCAN_INTERVAL,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.components.device_tracker import (PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['requests==2.11.1']

CONF_INTERVAL = 'interval'
KEEPALIVE_INTERVAL = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): vol.Coerce(str),
    vol.Optional(CONF_INTERVAL, default=1): vol.All(vol.Coerce(int),
                                                    vol.Range(min=1)),
    vol.Optional(CONF_ACCURACY, default=100): vol.Coerce(float),
    vol.Optional(CONF_SCAN_INTERVAL, default=1): vol.Coerce(int)
    })

def setup_scanner(hass, config, see):
    """Define constants."""
    import requests
    import json

    api_key = config[CONF_API_KEY]
    dev_id = config[CONF_ID]
    max_accuracy = config[CONF_ACCURACY]

    def get_position(now):
        """Get device position."""
        api_request = requests.post("https://www.googleapis.com/geolocation/v1/geolocate?key="+api_key)
        if r.ok:
            location = json.loads(api_request.text)

            accuracy = location["accuracy"]
            latitude = location["location"]["lat"]
            longitude = location["location"]["lng"]

            if max_accuracy is not None and\
                    accuracy > max_accuracy:
                _LOGGER.warning('Ignoring update because expected GPS '
                                'accuracy %s is not met: %s',
                                max_accuracy, accuracy)
                return None

            see(
                dev_id=dev_id,
                gps=(latitude, longitude),
                gps_accuracy=accuracy,
            )

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, get_position)

    update_minutes = list(range(0, 60, config[CONF_SCAN_INTERVAL]))

    track_utc_time_change(hass, get_position, second=0, minute=update_minutes)

    return True
