"""Support for IKEA Tradfri switches."""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback

from . import DOMAIN as TRADFRI_DOMAIN, KEY_API, KEY_GATEWAY
from .const import CONF_GATEWAY_ID

_LOGGER = logging.getLogger(__name__)

IKEA = 'IKEA of Sweden'
TRADFRI_SWITCH_MANAGER = 'Tradfri Switch Manager'


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Tradfri switches based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    api = hass.data[KEY_API][config_entry.entry_id]
    gateway = hass.data[KEY_GATEWAY][config_entry.entry_id]

    devices_commands = await api(gateway.get_devices())
    devices = await api(devices_commands)
    switches = [dev for dev in devices if dev.has_socket_control]
    if switches:
        async_add_entities(
            TradfriSwitch(switch, api, gateway_id) for switch in switches)


class TradfriSwitch(SwitchDevice):
    """The platform class required by Home Assistant."""

    def __init__(self, switch, api, gateway_id):
        """Initialize a switch."""
        self._api = api
        self._unique_id = "{}-{}".format(gateway_id, switch.id)
        self._switch = None
        self._socket_control = None
        self._switch_data = None
        self._name = None
        self._available = True
        self._gateway_id = gateway_id

        self._refresh(switch)

    @property
    def unique_id(self):
        """Return unique ID for switch."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        info = self._switch.device_info

        return {
            'identifiers': {
                (TRADFRI_DOMAIN, self._switch.id)
            },
            'name': self._name,
            'manufacturer': info.manufacturer,
            'model': info.model_number,
            'sw_version': info.firmware_version,
            'via_hub': (TRADFRI_DOMAIN, self._gateway_id),
        }

    async def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._async_start_observe()

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def should_poll(self):
        """No polling needed for tradfri switch."""
        return False

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._switch_data.state

    async def async_turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        await self._api(self._socket_control.set_state(False))

    async def async_turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        await self._api(self._socket_control.set_state(True))

    @callback
    def _async_start_observe(self, exc=None):
        """Start observation of switch."""
        from pytradfri.error import PytradfriError
        if exc:
            self._available = False
            self.async_schedule_update_ha_state()
            _LOGGER.warning("Observation failed for %s", self._name,
                            exc_info=exc)

        try:
            cmd = self._switch.observe(callback=self._observe_update,
                                       err_callback=self._async_start_observe,
                                       duration=0)
            self.hass.async_create_task(self._api(cmd))
        except PytradfriError as err:
            _LOGGER.warning("Observation failed, trying again", exc_info=err)
            self._async_start_observe()

    def _refresh(self, switch):
        """Refresh the switch data."""
        self._switch = switch

        # Caching of switchControl and switch object
        self._available = switch.reachable
        self._socket_control = switch.socket_control
        self._switch_data = switch.socket_control.sockets[0]
        self._name = switch.name

    @callback
    def _observe_update(self, tradfri_device):
        """Receive new state data for this switch."""
        self._refresh(tradfri_device)
        self.async_schedule_update_ha_state()
