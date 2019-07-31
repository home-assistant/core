"""Mikrotik status sensors."""
from datetime import timedelta
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

CLIENT = 'mikrotik_client'
MIKROTIK = 'mikrotik'
SENSOR = 'sensor'

SENSOR_SYSINFO = 'sysinfo'
SENSOR_CPU = 'cpu'
SENSOR_MEMORY = 'memory'
SENSOR_DISK = 'disk'
SENSOR_DOWNLOAD_SPEED = 'download_speed'
SENSOR_UPLOAD_SPEED = 'upload_speed'

ATTRIB_SYSINFO = ['board-name', 'serial-number',
                  'version', 'factory-firmware',
                  'firmware-type', 'current-firmware',
                  'upgrade-frimware', 'routerboard',
                  'cpu', 'total-memory',
                  'architecture-name']
ATTRIB_CPU = ['cpu',
              'cpu-frequency',
              'cpu-count']
ATTRIB_MEMORY = ['free-memory',
                 'total-memory']
ATTRIB_DISK = ['free-hdd-space',
               'total-hdd-space']
ATTRIB_DOWNLOAD_SPEED = ['name',
                         'rx-packets-per-second',
                         'rx-bits-per-second',
                         'fp-rx-packets-per-second',
                         'fp-rx-bits-per-second',
                         'rx-drops-per-second',
                         'rx-errors-per-second']
ATTRIB_UPLOAD_SPEED = ['name',
                       'tx-packets-per-second',
                       'tx-bits-per-second',
                       'fp-tx-packets-per-second',
                       'fp-tx-bits-per-second',
                       'tx-drops-per-second',
                       'tx-queue-drops-per-second',
                       'tx-errors-per-second']
ATTRIB_DOWNLOAD = ['name', 'tx-bytes']
ATTRIB_UPLOAD = ['name', 'rx-bytes']

PARAM_SPEED = {'interface': MTK_DEFAULT_WAN,
               'duration': '1s'}

SENSORS = {
    SENSOR_SYSINFO: ['System Info', None, 'mdi:switch',
                     'board-name',
                     ['/system/routerboard/getall',
                      '/system/resource/getall'],
                     ATTRIB_SYSINFO, None, None],
    SENSOR_CPU: ['CPU Load', '%', 'mdi:chip',
                 'cpu-load',
                 ['/system/resource/getall'],
                 ATTRIB_CPU, None],
    SENSOR_MEMORY: ['Memory Free', 'Mbytes',
                    'mdi:memory', 'free-memory',
                    ['/system/resource/getall'],
                    ATTRIB_MEMORY, None],
    SENSOR_DISK: ['Disk Free', 'Mbytes', 'mdi:harddisk',
                  'free-hdd-space',
                  ['/system/resource/getall'],
                  ATTRIB_DISK, None],
    SENSOR_DOWNLOAD_SPEED: ['Download Speed', 'Mbps',
                            'mdi:download-network',
                            'rx-bits-per-second',
                            ['/interface/monitor-traffic'],
                            ATTRIB_DOWNLOAD_SPEED,
                            PARAM_SPEED],
    SENSOR_UPLOAD_SPEED: ['Upload Speed', 'Mbps',
                          'mdi:upload-network',
                          'tx-bits-per-second',
                          ['/interface/monitor-traffic'],
                          ATTRIB_UPLOAD_SPEED, PARAM_SPEED],
}

async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the mikrotik sensors."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    client = hass.data[CLIENT]
    await client.update_info(host)
    data = hass.data[MIKROTIK][host]
    host_name = data.get('name', '')

    async_add_entities(
        [MikrotikSensor(hass, client, host, sensor_type, host_name)
         for sensor_type in discovery_info['sensors']])


class MikrotikSensor(Entity):
    """Representation of a mikrotik sensor."""

    def __init__(self, hass, client, host, sensor_type, host_name):
        """Initialize the sensor."""
        self.hass = hass
        self._host = host
        self._sensor_type = sensor_type
        self._client = client
        self._available = True
        self._state = None
        self._attrs = {}
        self._name = '{} {}'.format(host_name, SENSORS[sensor_type][0])
        self._unit = SENSORS[sensor_type][1]
        self._icon = SENSORS[sensor_type][2]
        self._item = SENSORS[sensor_type][3]
        if SENSOR not in self.hass.data[MIKROTIK][host]:
            self.hass.data[MIKROTIK][host][SENSOR] = {}
        self.hass.data[MIKROTIK][host][SENSOR][sensor_type] = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return the availability state."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    async def async_update(self, now=None):
        """Get the latest data and updates the state."""
        await self._client.update_sensors(self._host, self._sensor_type)
        data = self.hass.data[MIKROTIK][
            self._host][SENSOR][self._sensor_type]
        if data is None:
            self._available = False
            return
        self._available = True
        self._state = data.get('state')
        self._attrs = data.get('attrib')
