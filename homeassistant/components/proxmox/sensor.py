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
                PXMXSensor(
                    hass, name, 'Uptime', uptime, "min", 'mdi:clock-outline'))
        else:
            sensors.append(
                PXMXSensor(hass, name, 'VCPU Count', vcpus, None, 'mdi:chip'))
        sensors.append(
            PXMXSensor(hass, name, 'Memory', ram, "%", 'mdi:memory'))
        sensors.append(
            PXMXSensor(hass, name, 'Disk', disk, "%", 'mdi:harddisk'))
        sensors.append(
            PXMXSensor(hass, name, 'CPU', cpu, "%", 'mdi:chip'))
        sensors.append(
            PXMXSensor(
                hass, name, 'Max. Memory', mem_max, 'GB', 'mdi:memory'))
        sensors.append(
            PXMXSensor(
                hass, name, 'Memory Used', mem_used, 'GB', 'mdi:memory'))
        sensors.append(
            PXMXSensor(
                hass, name, 'Max. Disk', disk_max, 'GB', 'mdi:harddisk'))
        sensors.append(
            PXMXSensor(
                hass, name, 'Disk Used', disk_used, 'GB', 'mdi:harddisk'))
        sensors.append(
            PXMXSensor(hass, name, 'Status', status, None, None))

    async_add_entities(sensors)


class PXMXSensor(Entity):
    """Sensors to show the resource usages of Proxmox VE nodes & VMs."""

    def __init__(self, hass, node_name, sensor_name, value, unit, icon):
        """Initialize Proxmox VE sensor."""
        self._hass = hass
        self._node_name = node_name
        self._unit = unit
        self._icon = icon
        self._sensor_name = sensor_name
        self._value = value
        self._state = None
        self._is_available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} ({})'.format(self._sensor_name, self._node_name)

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

    def update(self):
        """Update the sensor."""
        nodes = self._hass.data[proxmox.DATA_PROXMOX_NODES]
        node = nodes[self._node_name]
        if not node:
            self._state = None
            self._is_available = False
        else:
            self._state = self._value(node)
            self._is_available = True


def uptime(node):
    """Return uptime of the given node in minutes."""
    return "{:.0f}".format(node['uptime']/60)


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
