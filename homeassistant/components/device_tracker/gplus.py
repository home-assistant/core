""".
Get location from Google Maps Geolocation API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.gmaps/
"""
import logging
import voluptuous as vol

from homeassistant.const import (CONF_TOKEN,
                                 CONF_SCAN_INTERVAL, CONF_ID, CONF_URL,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.components.device_tracker import (PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['requests>=2,<3']

CONF_INTERVAL = 'interval'
KEEPALIVE_INTERVAL = 1
CONF_SID = 'cookie_sid'
CONF_SSID = 'cookie_ssid'
CONF_HSID = 'cookie_hsid'
CONF_FREQ = 'data_freq'
CONF_AT = 'data_at'
CONF_ACCURACY = 'accuracy'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): vol.Coerce(str),
    vol.Required(CONF_URL): vol.Coerce(str),
    vol.Optional(CONF_ACCURACY, default=100): vol.Coerce(int),
    vol.Optional(CONF_INTERVAL, default=1): vol.All(vol.Coerce(int),
                                                    vol.Range(min=1)),
    vol.Optional(CONF_SCAN_INTERVAL, default=100): vol.Coerce(int)
})


def setup_scanner(hass, config, see):
    """Define constants."""
    import requests
    import re

    headers = {
        'Host': 'plus.google.com',
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:49.0) Gecko/20100101 Firefox/49.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
        'Referer': 'https://plus.google.com/',
        'X-Same-Domain': '1',
        'Connection': 'keep-alive',
    }


    max_accuracy = config[CONF_ACCURACY]
    id = config[CONF_ID]
    url = config[CONF_URL]
    cookie_sid = config[CONF_SID]
    cookie_hsid = config[CONF_HSID]
    cookie_ssid = config[CONF_SSID]
    data_freq = config[CONF_FREQ]
    data_at = config[CONF_AT]
    url = config[CONF_URL]
    regex_float = '-?\d+\.\d+'

    cookies = {
        'SID':  cookie_sid,
        'HSID': cookie_hsid,
        'SSID': cookie_ssid,
    }

    data = {
        'f.req': data_freq,
        'at': data_at,
    }

    def get_position(now):
        """Get device position."""
        api_request = requests.post(url, headers=headers, cookies=cookies,
                                    data=data)
        if api_request.ok:
            location = re.findall(regex_float, api_request.text)
            #_LOGGER.info(api_request.text)
            latitude = location[0]
            longitude = location[1]

            see(
                dev_id=id,
                gps=(latitude, longitude),
                gps_accuracy=max_accuracy,
            )

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, get_position)

    update_minutes = list(range(0, 60, config[CONF_SCAN_INTERVAL]))

    track_utc_time_change(hass, get_position, second=0, minute=update_minutes)

    return True
