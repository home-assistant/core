"""Support for sensors to show the resource usages of Proxmox VE."""
import homeassistant.components.proxmox as proxmox
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_ATTRIBUTION

ATTRIBUTION = 'Data provided by Proxmox'


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
                    hass, name, 'CPU', 'cpu_usage', '%', 'mdi:chip',
                    item, {}))
            sensors.append(
                PXMXSensor(
                    hass, name, 'Uptime', 'uptime', 'days',
                    'mdi:clock-outline', item, {}))
        else:
            sensors.append(
                PXMXSensor(
                    hass, name, 'CPU', 'cpu_usage', '%', 'mdi:chip', item,
                    {'vcpu_count': 'cpus'}))
        sensors.append(
            PXMXSensor(
                hass, name, 'Memory', 'ram_usage', '%', 'mdi:memory', item,
                {'mem_used': 'mem', 'max_memory': 'maxmem'}))
        sensors.append(
            PXMXSensor(
                hass, name, 'Disk', 'disk_usage', '%', 'mdi:harddisk', item,
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
        attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION
        }
        if 'type' in self._node and self._node['type'] == 'node':
            attributes['node'] = self._node['node']
        else:
            attributes['vmid'] = self._node['vmid']
            attributes['name'] = self._node['name']
        return attributes

    def update(self):
        """Update the sensor."""
        nodes = self._hass.data[proxmox.DATA_PROXMOX_NODES]
        node = nodes[self._name]
        self._node = node
        if not node:
            self._state = None
            self._is_available = False
        else:
            self._state = node[self._value]
            self._is_available = True
