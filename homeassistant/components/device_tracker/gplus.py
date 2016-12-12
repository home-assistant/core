""".

Get location from Google Plus Geolocation API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.gplus/
"""
import logging
import json
import voluptuous as vol
from bs4 import BeautifulSoup
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (CONF_SCAN_INTERVAL, CONF_ID, CONF_URL,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.components.device_tracker import (PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = []

CONF_INTERVAL = 'interval'
KEEPALIVE_INTERVAL = 1
CONF_SID = 'cookie_sid'
CONF_SSID = 'cookie_ssid'
CONF_HSID = 'cookie_hsid'
CONF_FREQ = 'data_freq'
CONF_HOME_URL = 'home_url'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_SID): cv.string,
    vol.Required(CONF_SSID): cv.string,
    vol.Required(CONF_HSID): cv.string,
    vol.Required(CONF_FREQ): cv.string,
    vol.Required(CONF_HOME_URL): cv.string,
    #    vol.Optional(CONF_ACCURACY, default=100): cv.positive_int,
    vol.Optional(CONF_INTERVAL, default=1): vol.All(cv.positive_int,
                                                    vol.Range(min=1)),
    vol.Optional(CONF_SCAN_INTERVAL, default=10): vol.All(cv.positive_int,
                                                          vol.Range(min=1, max=59)),
})


def setup_scanner(hass, config, see):
    """Setup Scanner."""
    import requests


#    max_accuracy = config[CONF_ACCURACY]
    conf_id = config[CONF_ID]
    url = config[CONF_URL]
    cookie_sid = config[CONF_SID]
    cookie_hsid = config[CONF_HSID]
    cookie_ssid = config[CONF_SSID]
    data_freq = config[CONF_FREQ]
    url = config[CONF_URL]
    hurl = config[CONF_HOME_URL]

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:49.0) Gecko/20100101 Firefox/49.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
        'X-Same-Domain': '1',
        'Connection': 'keep-alive',
    }

    cookies = {
        'SID':  cookie_sid,
        'HSID': cookie_hsid,
        'SSID': cookie_ssid,
    }

    data = {
        'f.req': data_freq,
        'at': None,
    }

    #update data['at'], which may change every 14 days.
    #Otherwise, Google rejects location queries.
    #visit the Google plus profile page, and extract the field from the first script in it
    def update_data_at():
        api_request = requests.get(
            hurl, headers=headers, cookies=cookies)
        soup = BeautifulSoup(api_request.text, 'html.parser')
        scripts = soup.find_all('script')
        script = (scripts[0]).contents[0]
        #print(script.body.attrs)
        _LOGGER.error(script)
        sdict = json.loads(script[25:-1])
        data['at'] = sdict['SNlM0e']
        _LOGGER.info(data['at'])

    def get_position(_):
        """Get device position."""
        if data['at'] is None:
            update_data_at()
        api_request = requests.post(url, headers=headers, cookies=cookies,
                                    data=data, timeout=15)
        if api_request.ok:
            ans = api_request.text
            matched_lines = [line for line in ans.split(
                '\n') if "www.google.com/maps/" in line]
            if len(matched_lines) == 0:
                _LOGGER.error("Google didn't send the location. Updating data['at']")
                update_data_at()

            line = matched_lines[0]
            words = line.split(',')
            latitude = words[12]
            longitude = words[13]
            accuracy = words[15]

            see(
                dev_id=conf_id,
                gps=(latitude, longitude),
                gps_accuracy=int(accuracy),
            )
        else:
            _LOGGER.error("Unable to update device position")


    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, get_position)

    update_minutes = list(range(0, 60, config[CONF_SCAN_INTERVAL]))

    track_utc_time_change(hass, get_position, second=0, minute=update_minutes)

    return True
