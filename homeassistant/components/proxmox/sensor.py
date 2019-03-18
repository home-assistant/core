import homeassistant.components.proxmox as proxmox
from homeassistant.helpers.entity import Entity

DOMAIN = 'proxmox'


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Proxmox VE sensors."""
    nodes = hass.data[proxmox.DATA_PROXMOX_NODES]
    sensors = []
    
    for node_name in nodes.keys():
        item = nodes[node_name]
        if 'type' in item and item['type'] == 'node':
            sensors.append(PXMXSensor(hass, node_name, 'Uptime',
                                      lambda node: "{:.0f}".format(node['uptime']/60), "min", 'mdi:clock-outline'))
        else:
            sensors.append(PXMXSensor(hass, node_name, 'VCPU Count',
                                      lambda node: node['cpus'], None, 'mdi:chip'))
        sensors.append(PXMXSensor(hass, node_name, 'Memory',
                                  lambda node: "{:.2f}".format(node['mem'] * 100 / node['maxmem']), "%", 'mdi:memory'))
        sensors.append(PXMXSensor(hass, node_name, 'Disk',
                                  lambda node: "{:.2f}".format(int(node['disk']) * 100 / int(node['maxdisk'])),
                                  "%", 'mdi:harddisk'))
        sensors.append(PXMXSensor(hass, node_name, 'CPU',
                                  lambda node: "{:.2f}".format(node['cpu'] * 100), "%", 'mdi:chip'))
        sensors.append(PXMXSensor(hass, node_name, 'Max. Memory',
                                  lambda node: "{:.2f}".format(node['maxmem']/1073741824), 'GB', 'mdi:memor'))
        sensors.append(PXMXSensor(hass, node_name, 'Memory Used',
                                  lambda node: "{:.2f}".format(node['mem']/1073741824), 'GB', 'mdi:memory'))
        sensors.append(PXMXSensor(hass, node_name, 'Max. Disk',
                                  lambda node: "{:.2f}".format(int(node['maxdisk'])/1073741824), 'GB', 'mdi:harddisk'))
        sensors.append(PXMXSensor(hass, node_name, 'Disk Used',
                                  lambda node: "{:.2f}".format(int(node['disk'])/1073741824), 'GB', 'mdi:harddisk'))
        sensors.append(PXMXSensor(hass, node_name, 'Status',
                                  lambda node: node['status'], None, None))

    async_add_entities(sensors)


class PXMXSensor(Entity):

    def __init__(self, hass, node_name, sensor_name, sensor_value, unit, icon):
        """Initialize Proxmox VE sensor."""
        self._hass = hass
        self._node_name = node_name
        self._unit = unit
        self._icon = icon
        self._sensor_name = sensor_name
        self._sensor_value = sensor_value
        self.update()

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
            self._state = self._sensor_value(node)
            self._is_available = True
