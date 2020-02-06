import logging
import synology_srm
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import config_validation

from homeassistant.const import (
    CONF_NAME,

    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,

    CONF_MONITORED_CONDITIONS,
)

DEFAULT_NAME = 'synology_srm'
DEFAULT_USERNAME = 'admin'
DEFAULT_PORT = 8001
DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False

POSSIBLE_MONITORED_CONDITIONS = {
    'base.encryption',
    'base.info',

    'core.ddns_extip',
    'core.ddns_record',
    'core.system_utilization',
    'core.network_nsm_device',

    'mesh.network_wanstatus',
    'mesh.network_wifidevice',
    'mesh.system_info',
}
DEFAULT_MONITORED_CONDITIONS = [
    'core.ddns_extip'
]

PLATFORM_SCHEMA = config_validation.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,

        vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED_CONDITIONS): vol.All(cv.ensure_list, [vol.In(POSSIBLE_MONITORED_CONDITIONS)])
    }
)

def setup_platform(hass, config, add_devices, discovery_info=None):
    add_devices([SynologySrm(config)])


class SynologySrm(Entity):

    def __init__(self, config):
        self.config = config

        self.client = synology_srm.Client(
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            https=config[CONF_SSL],
        )

        if not config[CONF_VERIFY_SSL]:
            self.client.http.disable_https_verify()

        self._state = None

        self._base_encryption = None
        self._base_info = None

        self._core_ddns_extip = None
        self._core_ddns_record = None
        self._core_system_utilization = None
        self._core_network_nsm_device = None

        self._mesh_network_wanstatus = None
        self._mesh_network_wifidevice = None
        self._mesh_system_info = None

    @property
    def name(self):
        return self.config.get(CONF_NAME)

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:router-wireless'

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return None

    @property
    def device_state_attributes(self):
        """Attributes."""
        return {
            'base': {
                'encryption': self._base_encryption,
                'info': self._base_info,
            },
            'core': {
                'ddns_extip': self._core_ddns_extip,
                'ddns_record': self._core_ddns_record,
                'system_utilization': self._core_system_utilization,
                'network_nsm_device': self._core_network_nsm_device
            },
            'mesh': {
                'network_wanstatus': self._mesh_network_wanstatus,
                'network_wifidevice': self._mesh_network_wifidevice,
                'system_info': self._mesh_system_info,
            },
        }

    def update(self):
        monitored_conditions = self.config.get(CONF_MONITORED_CONDITIONS)

        """Base"""
        if any(filter(lambda x: (x.startswith('base.')), monitored_conditions)):
            base = self.client.base

            if 'base.encryption' in monitored_conditions: self._base_encryption = base.encryption()
            if 'base.info' in monitored_conditions:       self._base_info = base.info()

        """Core"""
        if any(filter(lambda x: (x.startswith('core.')), monitored_conditions)):
            core = self.client.core

            if 'core.ddns_extip' in monitored_conditions:
                self._core_ddns_extip = core.ddns_extip()
                firstWan = next(iter(self._core_ddns_extip), None)
                self._state = firstWan and firstWan['ip']

            if 'core.ddns_record' in monitored_conditions:        self._core_ddns_record = core.ddns_record()
            if 'core.system_utilization' in monitored_conditions: self._core_system_utilization = core.system_utilization()
            if 'core.network_nsm_device' in monitored_conditions: self._core_network_nsm_device = core.network_nsm_device()

        """Mesh"""
        if any(filter(lambda x: (x.startswith('mesh.')), monitored_conditions)):
            mesh = self.client.mesh

            if 'mesh.network_wanstatus' in monitored_conditions: self._mesh_network_wanstatus = mesh.network_wanstatus()
            if 'mesh.network_wifidevice' in monitored_conditions: self._mesh_network_wifidevice = mesh.network_wifidevice()
            if 'mesh.system_info' in monitored_conditions: self._mesh_system_info = mesh.system_info()
            