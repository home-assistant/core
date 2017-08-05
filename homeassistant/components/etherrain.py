""".

Support for Etherrain/8.

"""
import logging

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
DOMAIN = 'etherrain'
STATE = 1
WATER_ON = 2
WATER_OFF = 3

LOGIN_RETRIES = 2

ER = {}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Etherrain component."""
    global ER
    ER = {}

    conf = config[DOMAIN]
    schema = 'http'

    server_origin = '{}://{}'.format(schema, conf[CONF_HOST])
    username = conf.get(CONF_USERNAME, None)
    password = conf.get(CONF_PASSWORD, None)

    ER['server_origin'] = server_origin
    ER['username'] = username
    ER['password'] = password

    hass.data[DOMAIN] = ER

    return login()


# pylint: disable=no-member
def login():
    """Login to the EtherRain API."""
    _LOGGER.info("Attempting to login to EtherRain")

    # ergetcfg.cgi?lu=admin\&lp=deadbeef
    url = '{0}/ergetcfg.cgi?lu={1}&lp={2}'.format(
        ER['server_origin'], ER['username'], ER['password'])
    req = requests.get(url, timeout=DEFAULT_TIMEOUT)

    if not req.ok:
        _LOGGER.error("Connection error logging into EtherRain")
        return False

    return True


# http://er_addr/result.cgi?xi=0:1:0:0:0:0:0:0:0
def _er_request(data=None):
    """Perform an EtherRain request."""
    valve = 0
    duration = 0
    cmd = 0
    if data is not 'None':
        cmd = data["command"]
        valve = data["valve"]
        duration = data["duration"]
    if cmd == STATE:
        # _LOGGER.info("Get state".format(valve,duration))
        url = '{0}/result.cgi?xs'.format(ER['server_origin'])
        duration = 0
    if cmd == WATER_OFF:
        # _LOGGER.info("Water off".format(valve,duration))
        url = '{0}/result.cgi?xr'.format(ER['server_origin'])
    if cmd == WATER_ON:
        _LOGGER.info("Set {0} to {1} minutes".format(valve, duration))
        valves = ["0", "0", "0", "0", "0", "0", "0", "0", "0"]
        valves[valve] = duration
        url = '{0}/result.cgi?xi=0:{1}:{2}:{3}:{4}:{5}:{6}:{7}:{8}'.format(
            ER['server_origin'], valves[1], valves[2], valves[3], valves[4],
            valves[5], valves[6], valves[7], valves[8])

    for _ in range(LOGIN_RETRIES):
        # _LOGGER.info("url is {0}".format(url))
        req = requests.get(url)
        # _LOGGER.info("Returned: {0}".format(req.status_code))

        if not req.ok:
            login()
        else:
            break
    else:
        _LOGGER.error("Unable to get API response from EtherRain")

    return req


# retrieve current status
# http://<er_addr>/result.cgi?xs
#
# <body>
#       EtherRain Device Status <br>
#       un:EtherRain 8
#       ma: 01.00.44.03.0A.01  <br>
#       ac: <br>
#       os: RD <br>
#       cs: OK <br>
#       rz: UK <br>
#       ri: 0 <br>
#       rn: 0 <br>
# </body>
def get_state(valve):
    """Get the current state of a valve."""
    data = {}
    data["valve"] = valve
    data["duration"] = 0
    data["command"] = STATE
    state = _er_request(data)
    # _LOGGER.info("got {0} from etherrain".format(state.text))
    status = {}
    for b_line in state.iter_lines():
        line = b_line.decode('utf8').strip()
        # _LOGGER.info("iterating: {0}".format(line))
        if ":" in line:
            attr, value = line.split(":")
            value = value.replace(" <br>", "").strip()
            attr = attr.strip()
            if attr in ['ac', 'os', 'cs', 'rz', 'ri', 'rn']:
                status[attr] = value

    # ri contains the last valve to run.  os is the current state of that
    # valve. (ready or busy)
    # (XXX: The valve number returned is 0-7 but the watering command
    # takes 1-8)
    if 'os' in status and status['os'] == 'WT':
        # _LOGGER.info("valve={0} and waiting".format(valve, status['ri']))
        return 1
    if 'ri' in status and int(status['ri']) == valve-1:
        if 'os' in status and status['os'] == 'RD':
            # _LOGGER.info("valve={0} and ready".format(valve, status['ri']))
            return 0
        if 'os' in status and status['os'] == 'BZ':
            # _LOGGER.info("valve={0} and busy".format(valve, status['ri']))
            return 1
    else:
        return 0


# pylint: disable=no-member
def change_state(valve_data):
    """Change the state of a valve."""
    _LOGGER.info("Change State: {0}".format(valve_data))
    return _er_request(data=valve_data)
