"""Support for switches to turn on/off Proxmox VE VMs/Containers."""
import homeassistant.components.proxmox as proxmox
from homeassistant.components.switch import SwitchDevice

DEVICE_CLASS = 'connectivity'
POWER_ICON = 'mdi:power'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up Proxmox VE switch."""
    nodes = hass.data[proxmox.DATA_PROXMOX_NODES]
    control = hass.data[proxmox.DATA_PROXMOX_CONTROL]
    sensors = []

    for name in nodes.keys():
        item = nodes[name]
        if 'type' not in item or item['type'] != 'node':
            if item['control']:
                sensor = PXMXSwitch(
                    hass, name, control['start'], control['shutdown'], item)
                sensors.append(sensor)

    async_add_entities(sensors)


class PXMXSwitch(SwitchDevice):
    """Switch to turn on / turn off a Proxmox VE Virtual Machine/Container."""

    def __init__(self, hass, name, start, shutdown, item):
        """Initialize monitor sensor."""
        self._hass = hass
        self._name = name
        self._start = start
        self._shutdown = shutdown
        self._vm_id = item['vmid']
        self._unique_id = proxmox.DOMAIN + '_switch_' + item['vmid']
        self._state = None
        self._is_available = False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} ({})'.format('Switch', self._name)

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return POWER_ICON

    @property
    def available(self):
        """Return True if Monitor is available."""
        return self._is_available

    async def async_turn_on(self, **kwargs):
        """Turn the VM/Container on."""
        node = self.get_node()
        if node:
            await self._start(node)

    async def async_turn_off(self, **kwargs):
        """Shutdown the VM/Container."""
        node = self.get_node()
        if node:
            await self._shutdown(node)

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return device attributes of the vm."""
        return {
            'vmid': self._vm_id
        }

    def update(self):
        """Update the sensor."""
        node = self.get_node()
        if not node:
            self._state = None
            self._is_available = False
        else:
            self._state = node['status'] == 'running'
            self._is_available = True

    def get_node(self):
        """Get current status."""
        nodes = self._hass.data[proxmox.DATA_PROXMOX_NODES]
        node = nodes[self._name]
        return node
