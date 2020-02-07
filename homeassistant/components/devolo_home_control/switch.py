"""Platform for light integration."""
import logging

from devolo_home_control_api.mprm_rest import get_sub_device_uid_from_element_uid

from homeassistant.components.switch import SwitchDevice

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Get all devices and add them to hass."""
    devices = hass.data[DOMAIN]["mprm"].binary_switch_devices

    devices_list = []
    for device in devices:
        if (
            get_sub_device_uid_from_element_uid([*device.binary_switch_property][0])
            is None
        ):
            # Normal binary switch device with one binary switch
            devices_list.append(
                DevoloSwitch(hass=hass, device_instance=device, sub_uid=None)
            )
        else:
            # Device with more than one binary switch
            for i in range(1, len(device.binary_switch_property) + 1):
                devices_list.append(
                    DevoloSwitch(hass=hass, device_instance=device, sub_uid=i)
                )
    add_entities(devices_list, False)


class DevoloSwitch(SwitchDevice):
    """Representation of an Awesome Light."""

    def __init__(self, hass, device_instance, sub_uid):
        """Initialize an devolo Switch."""
        self._device_instance = device_instance
        if sub_uid is not None:
            binary_switch = (
                "devolo.BinarySwitch:"
                + self._device_instance.device_uid
                + "#"
                + str(sub_uid)
            )
            consumption_property = (
                "devolo.Meter:" + self._device_instance.device_uid + "#" + str(sub_uid)
            )
        else:
            binary_switch = "devolo.BinarySwitch:" + self._device_instance.device_uid
            consumption_property = "devolo.Meter:" + self._device_instance.device_uid
        self._unique_id = binary_switch
        self._mprm = hass.data[DOMAIN]["mprm"]
        self._name = self._device_instance.name
        self._binary_switch_property = self._device_instance.binary_switch_property.get(
            binary_switch
        )
        self._is_on = self._binary_switch_property.state
        if hasattr(self._device_instance, "consumption_property"):
            self._consumption = self._device_instance.consumption_property.get(
                consumption_property
            ).current
        else:
            self._consumption = None
        self._subscriber = Subscriber(self._device_instance.name, device=self)
        self._mprm.publisher.register(
            self._device_instance.device_uid, self._subscriber
        )

    @property
    def unique_id(self):
        """Return the unique ID of switch."""
        return self._unique_id

    @property
    def device_id(self):
        """Return the ID of this switch."""
        return self._unique_id

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
        self._is_on = True
        self._mprm.set_binary_switch(element_uid=self._unique_id, state=True)

    def turn_off(self, **kwargs):
        """Switch off the device."""
        self._is_on = False
        self._mprm.set_binary_switch(element_uid=self._unique_id, state=False)

    def update(self, message=None):
        """Update the binary switch state and consumption."""
        if message[0].startswith("devolo.BinarySwitch"):
            self._is_on = self._device_instance.binary_switch_property[message[0]].state
        elif message[0].startswith("devolo.Meter"):
            self._consumption = self._device_instance.consumption_property[
                message[0]
            ].current
        else:
            _LOGGER.debug("No valid message received")
            _LOGGER.debug(message)
        self.schedule_update_ha_state()


class Subscriber:
    """Subscriber class for the publisher in mprm websocket class."""

    def __init__(self, name, device):
        """Initiate the device."""
        self.name = name
        self.device = device

    def update(self, message):
        """Trigger hass to update the device."""
        # TODO: Make this message to DEBUG before PR
        _LOGGER.info(f'{self.name} got message "{message}"')
        self.device.update(message)
