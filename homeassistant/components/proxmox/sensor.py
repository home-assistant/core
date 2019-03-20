"""Support for sensors to show the resource usages of Proxmox VE."""
import homeassistant.components.proxmox as proxmox
from homeassistant.helpers.entity import Entity


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up Proxmox VE sensors."""
    nodes = hass.data[proxmox.DATA_PROXMOX_NODES]
    sensors = []

    for name in nodes.keys():
        item = nodes[name]
        if 'type' in item and item['type'] == 'node':
            sensors.append(
                PXMXSensor(hass, name, 'CPU', cpu, '%', 'mdi:chip', item, {}))
            sensors.append(
                PXMXSensor(
                    hass, name, 'Uptime', uptime, 'days',
                    'mdi:clock-outline', item, {}))
        else:
            sensors.append(
                PXMXSensor(
                    hass, name, 'CPU', cpu, '%', 'mdi:chip', item,
                    {'vcpu_count': 'cpus'}))
        sensors.append(
            PXMXSensor(
                hass, name, 'Memory', ram, '%', 'mdi:memory', item,
                {'mem_used': 'mem', 'max_memory': 'maxmem'}))
        sensors.append(
            PXMXSensor(
                hass, name, 'Disk', disk, '%', 'mdi:harddisk', item,
                {'disk_used': 'disk', 'max_disk': 'maxdisk'}))

    async_add_entities(sensors)


class PXMXSensor(Entity):
    """Sensors to show the resource usages of Proxmox VE nodes & VMs."""

    def __init__(
            self, hass, name, sensor_name, value, unit, icon, node,
            attributes):
        """Initialize Proxmox VE sensor."""
        self._hass = hass
        self._name = name
        self._unit = unit
        self._icon = icon
        self._attributes = attributes
        self._node = node
        self._sensor_name = sensor_name
        self._value = value
        self._state = None
        self._is_available = False

    @property
    def unique_id(self):
        """Return the name of the sensor."""
        return

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} ({})'.format(self._sensor_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def available(self):
        """Return True if Monitor is available."""
        return self._is_available

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def state_attributes(self):
        """Return state attributes of the vm."""
        attributes = {}
        for key in self._attributes.keys():
            attributes[key] = self._node[self._attributes[key]]
        return attributes

    @property
    def device_state_attributes(self):
        """Return device attributes of the vm."""
        if 'type' in self._node and self._node['type'] == 'node':
            return {
                'node': self._node['node']
            }
        return {
            'vmid': self._node['vmid']
        }

    def update(self):
        """Update the sensor."""
        nodes = self._hass.data[proxmox.DATA_PROXMOX_NODES]
        node = nodes[self._name]
        self._node = node
        if not node:
            self._state = None
            self._is_available = False
        else:
            self._state = self._value(node)
            self._is_available = True


def uptime(node):
    """Return uptime of the given node in days."""
    return "{:.2f}".format(node['uptime']/86400)


def vcpus(node):
    """Return the no. of vcpus in the given vm."""
    return node['cpus']


def ram(node):
    """Return the memory usage as a percentage."""
    return "{:.2f}".format(node['mem'] * 100 / node['maxmem'])


def disk(node):
    """Return the disk usage as a percentage."""
    return "{:.2f}".format(int(node['disk']) * 100 / int(node['maxdisk']))


def cpu(node):
    """Return the cpu usage as a percentage."""
    return "{:.2f}".format(node['cpu'] * 100)


def mem_max(node):
    """Return the max. memory allocate to the given node in GB."""
    return "{:.2f}".format(node['maxmem']/1073741824)


def mem_used(node):
    """Return the memory used by the given node in GB."""
    return "{:.2f}".format(node['mem']/1073741824)


def disk_max(node):
    """Return the max. disk space allocate to the given node in GB."""
    return "{:.2f}".format(int(node['maxdisk'])/1073741824)


def disk_used(node):
    """Return the disk space used by the given node in GB."""
    return "{:.2f}".format(int(node['disk'])/1073741824)


def status(node):
    """Return the current status."""
    return node['status']
