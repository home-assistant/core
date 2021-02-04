"""Provides a binary sensor for Home Connect."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import (
    BSH_DOOR_STATE,
    BSH_REMOTE_CONTROL_ACTIVATION_STATE,
    BSH_REMOTE_START_ALLOWANCE_STATE,
    DOMAIN,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Home Connect binary sensor."""

    def get_entities():
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get("entities", {}).get("binary_sensor", [])
            entities += [HomeConnectBinarySensor(**d) for d in entity_dicts]
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectBinarySensor(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect."""

    def __init__(self, device, desc, sensor_type, device_class=None):
        """Initialize the entity."""
        super().__init__(device, desc)
        self._state = None
        self._device_class = device_class
        self._type = sensor_type
        if self._type == "door":
            self._update_key = BSH_DOOR_STATE
            self._false_value_list = (
                "BSH.Common.EnumType.DoorState.Closed",
                "BSH.Common.EnumType.DoorState.Locked",
            )
            self._true_value_list = ["BSH.Common.EnumType.DoorState.Open"]
        elif self._type == "remote_control":
            self._update_key = BSH_REMOTE_CONTROL_ACTIVATION_STATE
            self._false_value_list = [False]
            self._true_value_list = [True]
        elif self._type == "remote_start":
            self._update_key = BSH_REMOTE_START_ALLOWANCE_STATE
            self._false_value_list = [False]
            self._true_value_list = [True]

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return bool(self._state)

    @property
    def available(self):
        """Return true if the binary sensor is available."""
        return self._state is not None

    async def async_update(self):
        """Update the binary sensor's status."""
        state = self.device.appliance.status.get(self._update_key, {})
        if not state:
            self._state = None
        elif state.get("value") in self._false_value_list:
            self._state = False
        elif state.get("value") in self._true_value_list:
            self._state = True
        else:
            _LOGGER.warning(
                "Unexpected value for HomeConnect %s state: %s", self._type, state
            )
            self._state = None
        _LOGGER.debug("Updated, new state: %s", self._state)

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class
