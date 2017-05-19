"""
Support for Synology NAS Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.synologydsm/
"""
import logging
from datetime import timedelta

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PORT,
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS, EVENT_HOMEASSISTANT_START)
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

import voluptuous as vol

REQUIREMENTS = ['python-synology==0.1.0']

_LOGGER = logging.getLogger(__name__)

CONF_DISKS = 'disks'
CONF_VOLUMES = 'volumes'
DEFAULT_NAME = 'Synology DSM'
DEFAULT_PORT = 5000

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

_UTILISATION_MON_COND = {
    'cpu_other_load': ['CPU Load (Other)', '%', 'mdi:chip'],
    'cpu_user_load': ['CPU Load (User)', '%', 'mdi:chip'],
    'cpu_system_load': ['CPU Load (System)', '%', 'mdi:chip'],
    'cpu_total_load': ['CPU Load (Total)', '%', 'mdi:chip'],
    'cpu_1min_load': ['CPU Load (1 min)', '%', 'mdi:chip'],
    'cpu_5min_load': ['CPU Load (5 min)', '%', 'mdi:chip'],
    'cpu_15min_load': ['CPU Load (15 min)', '%', 'mdi:chip'],
    'memory_real_usage': ['Memory Usage (Real)', '%', 'mdi:memory'],
    'memory_size': ['Memory Size', 'Mb', 'mdi:memory'],
    'memory_cached': ['Memory Cached', 'Mb', 'mdi:memory'],
    'memory_available_swap': ['Memory Available (Swap)', 'Mb', 'mdi:memory'],
    'memory_available_real': ['Memory Available (Real)', 'Mb', 'mdi:memory'],
    'memory_total_swap': ['Memory Total (Swap)', 'Mb', 'mdi:memory'],
    'memory_total_real': ['Memory Total (Real)', 'Mb', 'mdi:memory'],
    'network_up': ['Network Up', 'Kbps', 'mdi:upload'],
    'network_down': ['Network Down', 'Kbps', 'mdi:download'],
}
_STORAGE_VOL_MON_COND = {
    'volume_status': ['Status', None, 'mdi:checkbox-marked-circle-outline'],
    'volume_device_type': ['Type', None, 'mdi:harddisk'],
    'volume_size_total': ['Total Size', None, 'mdi:chart-pie'],
    'volume_size_used': ['Used Space', None, 'mdi:chart-pie'],
    'volume_percentage_used': ['Volume Used', '%', 'mdi:chart-pie'],
    'volume_disk_temp_avg': ['Average Disk Temp', None, 'mdi:thermometer'],
    'volume_disk_temp_max': ['Maximum Disk Temp', None, 'mdi:thermometer'],
}
_STORAGE_DSK_MON_COND = {
    'disk_name': ['Name', None, 'mdi:harddisk'],
    'disk_device': ['Device', None, 'mdi:dots-horizontal'],
    'disk_smart_status': ['Status (Smart)', None,
                          'mdi:checkbox-marked-circle-outline'],
    'disk_status': ['Status', None, 'mdi:checkbox-marked-circle-outline'],
    'disk_exceed_bad_sector_thr': ['Exceeded Max Bad Sectors', None,
                                   'mdi:test-tube'],
    'disk_below_remain_life_thr': ['Below Min Remaining Life', None,
                                   'mdi:test-tube'],
    'disk_temp': ['Temperature', None, 'mdi:thermometer'],
}

_MONITORED_CONDITIONS = list(_UTILISATION_MON_COND.keys()) + \
    list(_STORAGE_VOL_MON_COND.keys()) + \
    list(_STORAGE_DSK_MON_COND.keys())

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(_MONITORED_CONDITIONS)]),
    vol.Optional(CONF_DISKS, default=None): cv.ensure_list,
    vol.Optional(CONF_VOLUMES, default=None): cv.ensure_list,
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the Synology NAS Sensor."""
    # pylint: disable=too-many-locals
    def run_setup(event):
        """Wait until HASS is fully initialized before creating.

        Delay the setup until Home Assistant is fully initialized.
        This allows any entities to be created already
        """
        # Setup API
        api = SynoApi(config.get(CONF_HOST), config.get(CONF_PORT),
                      config.get(CONF_USERNAME), config.get(CONF_PASSWORD),
                      hass.config.units.temperature_unit)

        sensors = [SynoNasUtilSensor(api, variable,
                                     _UTILISATION_MON_COND[variable])
                   for variable in config[CONF_MONITORED_CONDITIONS]
                   if variable in _UTILISATION_MON_COND]

        # Handle all Volumes
        volumes = config['volumes']
        if volumes is None:
            volumes = api.storage.volumes

        for volume in volumes:
            sensors += [SynoNasStorageSensor(api, variable,
                                             _STORAGE_VOL_MON_COND[variable],
                                             volume)
                        for variable in config[CONF_MONITORED_CONDITIONS]
                        if variable in _STORAGE_VOL_MON_COND]

        # Handle all Disks
        disks = config['disks']
        if disks is None:
            disks = api.storage.disks

        for disk in disks:
            sensors += [SynoNasStorageSensor(api, variable,
                                             _STORAGE_DSK_MON_COND[variable],
                                             disk)
                        for variable in config[CONF_MONITORED_CONDITIONS]
                        if variable in _STORAGE_DSK_MON_COND]

        add_devices_callback(sensors)

    # Wait until start event is sent to load this component.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, run_setup)


class SynoApi():
    """Class to interface with API."""

    # pylint: disable=too-many-arguments, bare-except
    def __init__(self, host, port, username, password, temp_unit):
        """Initialize the API wrapper class."""
        from SynologyDSM import SynologyDSM
        self.temp_unit = temp_unit

        try:
            self._api = SynologyDSM(host,
                                    port,
                                    username,
                                    password)
        except:
            _LOGGER.error("Error setting up Synology DSM")

        # Will be updated when `update` gets called.
        self.utilisation = self._api.utilisation
        self.storage = self._api.storage

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update function for updating api information."""
        self._api.update()


class SynoNasSensor(Entity):
    """Representation of a Synology Nas Sensor."""

    def __init__(self, api, variable, variableInfo, monitor_device=None):
        """Initialize the sensor."""
        self.var_id = variable
        self.var_name = variableInfo[0]
        self.var_units = variableInfo[1]
        self.var_icon = variableInfo[2]
        self.monitor_device = monitor_device
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        if self.monitor_device is not None:
            return "{} ({})".format(self.var_name, self.monitor_device)
        else:
            return self.var_name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.var_icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self.var_id in ['volume_disk_temp_avg', 'volume_disk_temp_max',
                           'disk_temp']:
            return self._api.temp_unit
        else:
            return self.var_units

    def update(self):
        """Get the latest data for the states."""
        if self._api is not None:
            self._api.update()


class SynoNasUtilSensor(SynoNasSensor):
    """Representation a Synology Utilisation Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        network_sensors = ['network_up', 'network_down']
        memory_sensors = ['memory_size', 'memory_cached',
                          'memory_available_swap', 'memory_available_real',
                          'memory_total_swap', 'memory_total_real']

        if self.var_id in network_sensors or self.var_id in memory_sensors:
            attr = getattr(self._api.utilisation, self.var_id)(False)

            if self.var_id in network_sensors:
                return round(attr / 1024.0, 1)
            elif self.var_id in memory_sensors:
                return round(attr / 1024.0 / 1024.0, 1)
        else:
            return getattr(self._api.utilisation, self.var_id)


class SynoNasStorageSensor(SynoNasSensor):
    """Representation a Synology Utilisation Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        temp_sensors = ['volume_disk_temp_avg', 'volume_disk_temp_max',
                        'disk_temp']

        if self.monitor_device is not None:
            if self.var_id in temp_sensors:
                attr = getattr(self._api.storage,
                               self.var_id)(self.monitor_device)

                if self._api.temp_unit == TEMP_CELSIUS:
                    return attr
                else:
                    return round(attr * 1.8 + 32.0, 1)
            else:
                return getattr(self._api.storage,
                               self.var_id)(self.monitor_device)
