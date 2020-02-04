"""Platform for light integration."""
import logging

from devolo_home_control_api.mprm_websocket import MprmWebsocket
from devolo_home_control_api.mydevolo import Mydevolo
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

DEFAULT_MYDEVOLO = "https://mydevolo.com"
DEFAULT_MPRM = "homecontrol.mydevolo.com"

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional("mydevolo", default=DEFAULT_MYDEVOLO): cv.string,
        vol.Optional("mprm", default=DEFAULT_MPRM): cv.string,
        vol.Required("gateway"): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Get all devices and add them to hass."""
    mprm_url = config.get("mprm")
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    mydevolo = Mydevolo.get_instance()
    mydevolo.user = user
    mydevolo.password = password
    mydevolo.url = config.get("mydevolo")

    gateway_id = mydevolo.gateway_ids[0]
    mprm_websocket = MprmWebsocket(gateway_id=gateway_id, url=mprm_url)

    devices = mprm_websocket.binary_switch_devices

    devices_list = []
    for device in devices:
        devices_list.append(
            DevoloSwitch(device_instance=device, web_socket=mprm_websocket)
        )
    add_entities(devices_list, True)


class DevoloSwitch(SwitchDevice):
    """Representation of an Awesome Light."""

    def __init__(self, device_instance, web_socket):
        """Initialize an devolo Switch."""
        self._device_instance = device_instance
        self._api = web_socket
        self._web_socket = web_socket
        self._name = device_instance.name
        self._is_on = None
        self._consumption = None
        self._subscriber_consumption = None
        self._subscriber_binary_state = None
        self.subscriber = Subscriber(self._device_instance.name, device=self)
        self._web_socket.publisher.register(
            self._device_instance.device_uid, self.subscriber
        )

    @property
    def unique_id(self):
        """Return the unique ID of switch."""
        return self._device_instance.device_uid

    @property
    def device_id(self):
        """Return the ID of this switch."""
        return self._device_instance.device_uid

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def is_on(self):
        """Return the state."""
        return self._is_on

    @property
    def current_power_w(self):
        """Return the current consumption."""
        return self._consumption

    def turn_on(self, **kwargs):
        """Switch on the device."""
        # TODO: Prepare for more than one switch
        self._is_on = True
        self._api.set_binary_switch(
            element_uid=[*self._device_instance.binary_switch_property][0], state=True
        )

    def turn_off(self, **kwargs):
        """Switch off the device."""
        # TODO: Prepare for more than one switch
        self._is_on = False
        self._api.set_binary_switch(
            element_uid=[*self._device_instance.binary_switch_property][0], state=False
        )

    def update(self, message=None, websocket_update=False):
        """Update the binary switch state and consumption."""
        if websocket_update:
            if message[0].startswith("devolo.BinarySwitch"):
                self._is_on = self._device_instance.binary_switch_property[
                    message[0]
                ].state
            elif message[0].startswith("devolo.Meter"):
                self._consumption = self._device_instance.consumption_property[
                    message[0]
                ].current
            else:
                _LOGGER.info("No valid message received")
        else:
            try:
                for (
                    binary_switch
                ) in self._device_instance.binary_switch_property.keys():
                    self._is_on = self._device_instance.binary_switch_property[
                        binary_switch
                    ].state
                for (
                    current_consumption
                ) in self._device_instance.consumption_property.keys():
                    self._consumption = self._device_instance.consumption_property[
                        current_consumption
                    ].current
            except (IndexError, AttributeError):
                # Not every binary switch device has a consumption
                self._consumption = None
        if websocket_update:
            self.schedule_update_ha_state()


class Subscriber:
    """Subscriber class for the publisher in mprm websocket class."""

    def __init__(self, name, device):
        """Initiate the device."""
        self.name = name
        self.device = device

    def update(self, message):
        """Trigger hass to update the device."""
        # Make this message to DEBUG before PR
        _LOGGER.info(f'{self.name} got message "{message}"')
        self.device.update(websocket_update=True, message=message)
