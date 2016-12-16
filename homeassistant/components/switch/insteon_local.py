"""
    Support for Insteon local Switches.
    
    For more details about this platform, please refer to the documentation at
    
    --
    Example platform config
    --
    
    insteon_local:
    host: YOUR HUB IP
    username: YOUR HUB USERNAME
    password: YOUR HUB PASSWORD
    
    --
    Example platform config
    --
    
    switch:
    - platform: insteon_local
    switches:
    dining_room:
    device_id: 30DA8A
    name: Dining Room
    living_room:
    device_id: 30D927
    name: Living Room
    
    """
from homeassistant.components.switch import SwitchDevice
import homeassistant.components.insteon_local as INSTEON_LOCAL

DEPENDENCIES = ['insteon_local']

DOMAIN = "switch"

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon local switch platform."""
    devs = []
    if len(config) > 0:
        items = config['switches'].items()
        
        # todo: use getLinked instead? We'd still need to include name and deviceid in config, and it takes a while to execute because of the sleeps when hitting the buffer though, so maybe it's not a priority
        for key, switch in items:
            # todo: get device type and determine whether to use a dimmer or switch
            device = INSTEON_LOCAL.switch(switch['device_id'])
            device.beep()
            devs.append(InsteonLocalSwitchDevice(device, switch['name']))
        add_devices(devs)


class InsteonLocalSwitchDevice(SwitchDevice):
    """An abstract Class for an Insteon node."""
    
    def __init__(self, node, name):
        """Initialize the device."""
        self.node = node
        self.node.deviceName = name
        self._value = 0
    
    @property
    def name(self):
        """Return the the name of the node."""
        
        return self.node.deviceName
    
    @property
    def unique_id(self):
        """Return the ID of this insteon node."""
        return self.node.deviceId
    
    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._value / 100 * 255
    
    def update(self):
        """Update state of the sensor."""
        resp = self.node.status()
        if resp is None:
            self._value = 0
        else:
            self._value = int(resp['cmd2'], 16)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._value != 0
    
    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_INSTEON_LOCAL
    
    def turn_on(self, **kwargs):
        """Turn device on."""
        self.node.on(100)
    
    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.offInstant()

