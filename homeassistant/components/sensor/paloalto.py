"""
Support for getting statistical data from a Palo Alto device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.paloalto/
"""
import ssl
import logging
import urllib.request
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import xml.etree.ElementTree as ET

from enum import Enum
from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_API_KEY, CONF_IP_ADDRESS,
                                 CONF_SSL, CONF_VERIFY_SSL,
                                 CONF_MONITORED_CONDITIONS)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'PaloAlto'
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

CONST_COMMAND = "COMMAND"
CONST_OPS_ENDPOINT = '/api/?type=op&cmd=COMMAND'
CONST_CONFIG_ENDPOINT = '/api/?type=config&action=get&xpath=COMMAND'

PA_OPS_ACTIVE_USERS = "<show><admins></admins></show>"
PA_CONF_SYS_INFO = "<show><system><info></info></system></show>"
PA_CONF_GP_USERS = "<show><global-protect-portal><current-user>" \
                    "</current-user></global-protect-portal></show>"
PA_CONF_TEMPERATURE = "<show><system><environmentals><thermal>" \
                        "</thermal></environmentals></system></show>"

SCAN_INTERVAL = timedelta(seconds=120)

MONITORED_CONDITIONS = {
    'host_name': ['Host Name', 'x', 'mdi:fire'],
    'up_time': ['Up Time', 'x', 'mdi:clock'],
    'serial_no': ['Serial Number', 'x', 'mdi:counter'],
    'sw_version': ['Software Version', 'x', 'mdi:counter'],
    'gp_version': ['Global protect Version', 'x', 'mdi:counter'],
    'logdb_version': ['LogDB Version', 'x', 'mdi:book-open'],
    'operation_mode': ['Operation Mode', 'x', 'mdi:book-open'],
    'core_temp': ['Core Temperature', 'x', 'mdi:oil-temperature'],
    'sys_temp': ['System Temperature', 'x', 'mdi:oil-temperature'],
    'gp_user_count': ['Global Protect User Count', 'vpn users', 'mdi:counter'],
    'gp_users': ['Global Protect Users', 'vpn users', 'mdi:account-multiple'],
    'loggedin_user_count': ['Loggedin User Count', 'users', 'mdi:counter'],
    'loggedin_users': ['Loggedin Users', 'users', 'mdi:account-multiple'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=list(MONITORED_CONDITIONS)):
    vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Palo Alto VPN User Sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_IP_ADDRESS)
    use_ssl = config.get(CONF_SSL)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    api_key = config.get(CONF_API_KEY)
    sensors = []

    try:
        api = PaloAltoApi(host, use_ssl, verify_ssl, api_key)
        for condition in config[CONF_MONITORED_CONDITIONS]:
            sensor = PaloAltoSensor(hass, api, name, condition)
            sensors.append(sensor)
        add_devices(sensors, True)
    except Exception as err:
        _LOGGER.error("Failed to setup Palo Alto Sensor. Error: " + str(err))


class PaloAltoSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, hass, api, name, variable):
        """Initialize the sensor."""
        self._hass = hass
        self._api = api
        self._name = name
        self._var_id = variable

        variable_info = MONITORED_CONDITIONS[variable]
        self._var_name = variable_info[0]
        self._var_units = variable_info[1]
        self._var_icon = variable_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._name, self._var_name)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._var_icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._api.data[self._var_id]

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._api.available

    def update(self):
        """Get the latest data and updates the state."""
        self._api.update()


class PaloAltoApi(object):
    """The class for handling the data retrieval from Palo Alto Device."""

    def __init__(self, host, use_ssl, verify_ssl, api_key):
        """Initialize the Palo Alto API."""
        self._host = host
        self._use_ssl = use_ssl
        self._verify_ssl = verify_ssl
        self._api_key = api_key
        self._usersdata = None
        self._sysinfo = None
        self._gp_users = None
        self._temperature = None
        self.available = True
        self._sensors = {}

    @property
    def data(self):
        """Return data."""
        return self._sensors

    def get_uri_scheme(self, use_ssl):
        """Return proper uril scheme based on config setting."""
        return 'https://' if use_ssl else 'http://'

    def get_resource(self, use_ssl, host, api_key, endpoint):
        """Prepare the URL."""
        uri_scheme = self.get_uri_scheme(use_ssl)
        if endpoint == EndPointType.Operational:
            return "{}{}{}&key={}".format(uri_scheme, self._host,
                                          CONST_OPS_ENDPOINT, self._api_key)
        else:
            return "{}{}{}&key={}".format(uri_scheme, self._host,
                                          CONST_CONFIG_ENDPOINT, self._api_key)

    def http_request(self, url):
        """HTTP request to the Palo Alto device."""
        content = None
        context = None
        try:
            if self._use_ssl and not self._verify_ssl:
                context = ssl._create_unverified_context()
            response = urllib.request.urlopen(url, context=context)
            content = response.read()
        except Exception as ex:
            _LOGGER.error(str(ex))
            content = None

        return content

    def update(self):
        """Get Operational and Configuration urls."""
        ops_url = self.get_resource(self._use_ssl, self._host,
                                    self._api_key, EndPointType.Operational)

        users_url = ops_url.replace(CONST_COMMAND, PA_OPS_ACTIVE_USERS)
        self._usersdata = self.http_request(users_url)

        sysinfo_url = ops_url.replace(CONST_COMMAND, PA_CONF_SYS_INFO)
        self._sysinfo = self.http_request(sysinfo_url)

        gp_users_url = ops_url.replace(CONST_COMMAND, PA_CONF_GP_USERS)
        self._gp_users = self.http_request(gp_users_url)

        temperature_url = ops_url.replace(CONST_COMMAND, PA_CONF_TEMPERATURE)
        self._temperature = self.http_request(temperature_url)

        """parse the xml data"""
        self.parse_data()

    def parse_globalprotect_users(self):
        """Parses global protect users xml."""
        user_count = 0
        vpn_users = []
        root = ET.fromstring(self._gp_users)
        nodes = root.findall('result/gp-portal-users/user')
        for user in nodes:
            user_count += 1
            vpn_users.append(user.find('username').text)

        if user_count != 0:
            self._sensors["gp_users"] = ', '.join(vpn_users)
        else:
            self._sensors["gp_users"] = "None"
        self._sensors["gp_user_count"] = user_count

    def parse_temperature(self):
        """Parses environment/temperature values."""
        root = ET.fromstring(self._temperature)
        nodes = root.findall('result/thermal/Slot1/entry/DegreesC')
        self._sensors["core_temp"] = round(float(nodes[0].text), 2)
        self._sensors["sys_temp"] = round(float(nodes[1].text), 2)

    def parse_system_info(self):
        """Parses System Information."""
        root = ET.fromstring(self._sysinfo)
        sys_node = root.findall('result/system')
        self._sensors["up_time"] = sys_node[0].find('uptime').text
        self._sensors["serial_no"] = sys_node[0].find('serial').text
        self._sensors["host_name"] = sys_node[0].find('hostname').text
        self._sensors["sw_version"] = sys_node[0].find('sw-version').text
        self._sensors["logdb_version"] = sys_node[0].find(
                    'logdb-version').text
        self._sensors["operation_mode"] = sys_node[0].find(
                    'operational-mode').text
        self._sensors["gp_version"] = sys_node[0].find(
                    'global-protect-client-package-version').text

    def parse_active_users(self):
        """Parses Active Users XML."""
        root = ET.fromstring(self._usersdata)
        nodes = root.findall('result/admins/entry')
        count = 0
        users = []
        for item in nodes:
            count += 1
            users.append(item.find('admin').text)

        if count > 0:
            self._sensors["loggedin_users"] = ', '.join(users)
        else:
            self._sensors["loggedin_users"] = "none"

        self._sensors["loggedin_user_count"] = count

    def parse_data(self):
        """Parses data and populates sensors."""
        self.parse_globalprotect_users()
        self.parse_temperature()
        self.parse_system_info()
        self.parse_active_users()


class EndPointType(Enum):
    """Enum that indicates that type of endpoint that is."""

    Operational = "operational"
    Configuration = "configuration"
