"""Platform for light integration."""
import logging

from devolo_home_control_api.homecontrol import get_sub_device_uid_from_element_uid

from homeassistant.components.switch import SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

logging.basicConfig(level=logging.DEBUG)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all devices and setup the switch devices via config entry."""
    devices = hass.data[DOMAIN]["homecontrol"].binary_switch_devices

    devices_list = []
    for device in devices:
        for i in range(len(device.binary_switch_property)):
            devices_list.append(
                DevoloSwitch(
                    hass=hass,
                    device_instance=device,
                    sub_uid=get_sub_device_uid_from_element_uid(
                        [*device.binary_switch_property][i]
                    ),
                )
            )
    async_add_entities(devices_list, False)


class DevoloSwitch(SwitchDevice):
    """Representation of an Awesome Light."""

    def __init__(self, hass, device_instance, sub_uid):
        """Initialize an devolo Switch."""
        self._device_instance = device_instance

        # Create the unique ID
        if sub_uid is not None:
            self._unique_id = self._device_instance.uid + "#" + str(sub_uid)
        else:
            self._unique_id = self._device_instance.uid

        self._homecontrol = hass.data[DOMAIN]["homecontrol"]
        self._name = self._device_instance.itemName
        self._available = self._device_instance.is_online()

        # Get the brand and model information
        try:
            self._brand = self._device_instance.brand
            self._model = self._device_instance.name
        except AttributeError:
            self._brand = None
            self._model = None

        self._binary_switch_property = self._device_instance.binary_switch_property.get(
            "devolo.BinarySwitch:" + self._unique_id
        )
        self._is_on = self._binary_switch_property.state

        if hasattr(self._device_instance, "consumption_property"):
            self._consumption = self._device_instance.consumption_property.get(
                "devolo.Meter:" + self._unique_id
            ).current
        else:
            self._consumption = None
        self._subscriber = Subscriber(self._device_instance.itemName, device=self)
        self._homecontrol.publisher.register(
            self._device_instance.uid, self._subscriber
        )

    @property
    def unique_id(self):
        """Return the unique ID of the switch."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": self._brand,
            "model": self._model,
        }

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

    @property
    def available(self):
        """Return the online state."""
        return self._available

    def turn_on(self, **kwargs):
        """Switch on the device."""
        self._is_on = True
        self._binary_switch_property.set_binary_switch(state=True)

    def turn_off(self, **kwargs):
        """Switch off the device."""
        self._is_on = False
        self._binary_switch_property.set_binary_switch(state=False)

    def update(self, message=None):
        """Update the binary switch state and consumption."""
        if message[0].startswith("devolo.BinarySwitch"):
            self._is_on = self._device_instance.binary_switch_property[message[0]].state
        elif message[0].startswith("devolo.Meter"):
            self._consumption = self._device_instance.consumption_property[
                message[0]
            ].current
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
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
        _LOGGER.debug(f'{self.name} got message "{message}"')
        self.device.update(message)
