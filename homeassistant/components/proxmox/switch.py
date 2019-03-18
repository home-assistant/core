import homeassistant.components.proxmox as proxmox
from homeassistant.components.switch import SwitchDevice

DOMAIN = 'proxmox'


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Proxmox VE switch."""
    nodes = hass.data[proxmox.DATA_PROXMOX_NODES]
    control = hass.data[proxmox.DATA_PROXMOX_CONTROL]
    sensors = []

    for node_name in nodes.keys():
        item = nodes[node_name]
        if 'type' not in item or item['type'] != 'node':
            sensors.append(PXMXBinarySensor(hass, node_name, 'Is Running', lambda node: 'running' == node['status'],
                                            control['start'], control['stop']))

    async_add_entities(sensors)


class PXMXBinarySensor(SwitchDevice):

    def __init__(self, hass, node_name, sensor_name, sensor_value, start, stop):
        """Initialize monitor sensor."""
        self._hass = hass
        self._node_name = node_name
        self._sensor_name = sensor_name
        self._sensor_value = sensor_value
        self._start = start
        self._stop = stop
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

    async def async_turn_on(self, **kwargs):
        node = self.get_node()
        if node:
            await self._start(node)

    async def async_turn_off(self, **kwargs):
        node = self.get_node()
        if node:
            await self._stop(node)

    def update(self):
        """Update the sensor."""
        node = self.get_node()
        if not node:
            self._state = None
            self._is_available = False
        else:
            self._state = self._sensor_value(node)
            self._is_available = True

    def get_node(self):
        nodes = self._hass.data[proxmox.DATA_PROXMOX_NODES]
        node = nodes[self._node_name]
        return node
