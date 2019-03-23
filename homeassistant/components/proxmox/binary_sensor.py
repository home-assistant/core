"""Support for binary sensors to display Proxmox VE data."""
import homeassistant.components.proxmox as proxmox
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_ATTRIBUTION

DEVICE_CLASS = 'connectivity'
ATTRIBUTION = 'Data provided by Proxmox'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up Proxmox VE binary sensor."""
    nodes = hass.data[proxmox.DATA_PROXMOX_NODES]
    sensors = []
    attributes = {
        'status': 'status',
        'vcpu_count': 'cpus',
        'mem_used': 'mem',
        'max_memory': 'maxmem',
        'disk_used': 'disk',
        'max_disk': 'maxdisk'
    }

    for node_name in nodes.keys():
        item = nodes[node_name]
        if 'type' not in item or item['type'] != 'node':
            sensor = PXMXBinarySensor(hass, node_name, item, attributes)
            sensors.append(sensor)

    async_add_entities(sensors)


class PXMXBinarySensor(BinarySensorDevice):
    """Define a binary sensor for Proxmox VE VM/Container state."""

    def __init__(self, hass, node_name, item, attributes):
        """Initialize Proxmox VE binary sensor."""
        self._hass = hass
        self._node_name = node_name
        self._is_available = False
        self._state = None
        self._attributes = attributes
        self._vm_id = item['vmid']
        self._vm_name = item['name']
        self._item = item
        self._unique_id = proxmox.DOMAIN + '_status_' + item['vmid']

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} ({})'.format('Status', self._node_name)

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def available(self):
        """Return True if sensor is available."""
        return self._is_available

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return DEVICE_CLASS

    @property
    def state_attributes(self):
        """Return state attributes of the vm."""
        attributes = {}
        for key in self._attributes.keys():
            attributes[key] = self._item[self._attributes[key]]
        return attributes

    @property
    def device_state_attributes(self):
        """Return device attributes of the vm."""
        return {
            'vmid': self._vm_id,
            'name': self._vm_name,
            ATTR_ATTRIBUTION: ATTRIBUTION
        }

    def update(self):
        """Update the sensor."""
        nodes = self._hass.data[proxmox.DATA_PROXMOX_NODES]
        node = nodes[self._node_name]
        self._item = node
        if not node:
            self._state = None
            self._is_available = False
        else:
            self._state = node['status'] == 'running'
            self._is_available = True
