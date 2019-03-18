import homeassistant.components.proxmox as proxmox
from homeassistant.components.switch import SwitchDevice

DOMAIN = 'proxmox'


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Proxmox VE binary sensor."""
    nodes = hass.data[proxmox.DATA_PROXMOX_NODES]
    sensors = []

    for node_name in nodes.keys():
        item = nodes[node_name]
        if 'type' not in item or item['type'] != 'node':
            sensors.append(PXMXBinarySensor(hass, node_name, 'Is Running', lambda node: 'running' == node['status']))

    async_add_entities(sensors)


class PXMXBinarySensor(SwitchDevice):

    def __init__(self, hass, node_name, sensor_name, sensor_value):
        """Initialize Proxmox VE binary sensor."""
        self._hass = hass
        self._node_name = node_name
        self._sensor_name = sensor_name
        self._sensor_value = sensor_value
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} ({})'.format(self._sensor_name, self._node_name)

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def available(self):
        """Return True if Monitor is available."""
        return self._is_available

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
