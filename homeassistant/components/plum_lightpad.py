"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/plum_lightpad
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers import discovery

REQUIREMENTS = ['plumlightpad==0.0.8']

DOMAIN = 'plum_lightpad'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Setup the Plum Lightpad component."""
    from plumlightpad import Plum

    conf = config[DOMAIN]
    plum = Plum(conf.get(CONF_USERNAME), conf.get(CONF_PASSWORD))  # TODO support just house token?

    plum_manager = PlumManager(hass, plum)
    hass.data['plum'] = plum_manager

    @callback
    def cleanup(event):
        """Clean up resources."""
        print("Mr. Clean Spic and Span")
        # plum.cleanup()
        # shut down listeners, ports, etc.

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    await plum_manager.discover()

    discovery.load_platform(hass, 'light', DOMAIN, None, conf)
    discovery.load_platform(hass, 'sensor', DOMAIN, None, conf)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, None, conf)

    return True


class PlumManager(object):
    """Representation of all known Plum entities."""

    def __init__(self, hass, plum):
        """Initialize the Plum Manager."""
        self.plum = plum
        self._lightpads = {}
        self._loads = {}
        self._logical_load_listeners = {}
        self._power_listeners = {}
        self._motion_listeners = {}
        self.hass = hass

    async def discover(self):
        await self.plum.discover()

        for lpid, data in self.plum.get_lightpads().items():
            metrics = self.plum.get_lightpad_metrics(lpid)
            self._lightpads[lpid] = Lightpad(lpid=lpid, data=data, manager=self, metrics=metrics)

        for llid, data in self.plum.get_logical_loads().items():
            metrics = self.plum.get_logical_load_metrics(llid)
            self._loads[llid] = LogicalLoad(llid=llid, data=data, manager=self, metrics=metrics)

    def add_load_listener(self, llid, callback):
        self._logical_load_listeners[llid] = callback  # todo handle multiple

    def add_power_listener(self, lpid, callback):
        self._power_listeners[lpid] = callback  # todo handle multiple

    def add_pir_listener(self, lpid, callback):
        self._motion_listeners[lpid] = callback  # todo handle multiple

    @property
    def lightpads(self):
        return self._lightpads

    @property
    def logical_loads(self):
        return self._loads

    def processEvent(self, lpid, event):
        print("PlumManager::processEvent", lpid, event)

        lightpad = self._lightpads[lpid]

        if event['type'] == 'dimmerchange':
            self._logical_load_listeners[lightpad.llid](event['level'])

        if event['type'] == 'power':
            self._power_listeners[lightpad.llid](event['watts'])

        if event['type'] == 'configchange':
            print('configchange', event['changes'])

        if event['type'] == 'pirSignal':
            print('pirSignal', event['signal'])
            self._motion_listeners[lpid](event['signal'])


class Lightpad(object):

    def __init__(self, lpid, manager, data, metrics):
        """Initialize the light."""
        self.lpid = lpid
        self._data = data
        self._config = data['config']
        self._metrics = metrics
        self._manager = manager
        self.config_change_listener = None
        manager.plum.register_event_listener(lpid, self.__process_event)
        print(self._data)
        print(self._metrics)

    def __process_event(self, event):
        self._manager.processEvent(self.lpid, event)
        if event['type'] == 'configchange':
            self._config = event['changes']
            if self.config_change_listener is not None:
                self.config_change_listener()

    def add_config_change_listener(self, listener):
        self.config_change_listener = listener

    @property
    def llid(self):
        return self._data["logical_load_id"]

    @property
    def name(self):
        return self._data["name"]

    @property
    def glowColor(self):
        return self._config['glowColor']

    @property
    def glowTimeout(self):
        return self._config['glowTimeout']

    @property
    def glowFade(self):
        return self._config['glowFade']

    @property
    def glowEnabled(self):
        return self._config['glowEnabled']

    @property
    def forceGlow(self):
        return self._config['forceGlow']

    @property
    def glowIntensity(self):
        return self._config['glowIntensity']

    @property
    def glowTracksDimmer(self):
        return self._config['glowTracksDimmer']

    def set_config(self, config):
        self._manager.plum.set_lightpad_config(self.lpid, config)

    def set_glow_color(self, r, g, b, w):
        self._manager.plum.set_glow_color(lpid=self.lpid, r=r, g=g, b=b, w=w)

class LogicalLoad(object):
    def __init__(self, llid, metrics, data, manager):
        """Initialize the light."""
        self.llid = llid
        self._data = data
        self._metrics = metrics
        self._manager = manager

    @property
    def level(self):
        return self._metrics['lightpad_metrics'][0]['level']

    @property
    def power(self):
        return self._metrics['power']

    @property
    def name(self):
        return self._data['name']

    def brightness(self, brightness):
        self._manager.plum.set_logical_load_level(self.llid, brightness)

    def on(self):
        self._manager.plum.turn_logical_load_on(self.llid)

    def off(self):
        self._manager.plum.turn_logical_load_off(self.llid)
