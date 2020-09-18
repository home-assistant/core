"""Platform for switch integration."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all devices and setup the switch devices via config entry."""
    devices = hass.data[DOMAIN]["homecontrol"].binary_switch_devices

    entities = []
    for device in devices:
        for binary_switch in device.binary_switch_property:
            # Exclude the binary switch which also has multi_level_switches here,
            # because those are implemented as light entities now.
            if not hasattr(device, "multi_level_switch_property"):
                entities.append(
                    DevoloSwitch(
                        homecontrol=hass.data[DOMAIN]["homecontrol"],
                        device_instance=device,
                        element_uid=binary_switch,
                    )
                )
    async_add_entities(entities)


class DevoloSwitch(SwitchEntity):
    """Representation of a switch."""

    def __init__(self, homecontrol, device_instance, element_uid):
        """Initialize an devolo Switch."""
        self._device_instance = device_instance

        # Create the unique ID
        self._unique_id = element_uid

        self._homecontrol = homecontrol
        self._name = self._device_instance.item_name

        # This is not doing I/O. It fetches an internal state of the API
        self._available = self._device_instance.is_online()

        # Get the brand and model information
        self._brand = self._device_instance.brand
        self._model = self._device_instance.name

        self._binary_switch_property = self._device_instance.binary_switch_property.get(
            self._unique_id
        )
        self._is_on = self._binary_switch_property.state

        if hasattr(self._device_instance, "consumption_property"):
            self._consumption = self._device_instance.consumption_property.get(
                self._unique_id.replace("BinarySwitch", "Meter")
            ).current
        else:
            self._consumption = None

        self.subscriber = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.subscriber = Subscriber(
            self._device_instance.item_name, callback=self.sync
        )
        self._homecontrol.publisher.register(
            self._device_instance.uid, self.subscriber, self.sync
        )

    @property
    def unique_id(self):
        """Return the unique ID of the switch."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device_instance.uid)},
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
        self._binary_switch_property.set(state=True)

    def turn_off(self, **kwargs):
        """Switch off the device."""
        self._is_on = False
        self._binary_switch_property.set(state=False)

    def sync(self, message=None):
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
            _LOGGER.debug("No valid message received: %s", message)
        self.schedule_update_ha_state()


class Subscriber:
    """Subscriber class for the publisher in mprm websocket class."""

    def __init__(self, name, callback):
        """Initiate the device."""
        self.name = name
        self.callback = callback

    def update(self, message):
        """Trigger hass to update the device."""
        _LOGGER.debug('%s got message "%s"', self.name, message)
        self.callback(message)
