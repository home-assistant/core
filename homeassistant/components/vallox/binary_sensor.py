"""Support for the Vallox ventilation unit binary sensors."""

import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_VALLOX_STATE_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the binary sensor device."""
    if discovery_info is None:
        return

    name = hass.data[DOMAIN]["name"]
    state_proxy = hass.data[DOMAIN]["state_proxy"]

    binary_sensors = [
        ValloxFilterOverdueBinarySensor(
            name=f"{name} filter overdue",
            state_proxy=state_proxy,
            metric_key="A_CYC_REMAINING_TIME_FOR_FILTER",
            device_class=None,
            icon="mdi:filter",
        )
    ]

    async_add_entities(binary_sensors, update_before_add=False)


class ValloxBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor device."""

    def __init__(self, name, state_proxy, metric_key, device_class, icon):
        """Initialize the binary sensor."""
        self._name = name
        self._state_proxy = state_proxy
        self._metric_key = metric_key
        self._device_class = device_class
        self._icon = icon
        self._is_on = False
        self._available = False

    @property
    def should_poll(self):
        """Do not poll the device."""
        return False

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    async def async_added_to_hass(self):
        """Call to update."""
        async_dispatcher_connect(
            self.hass, SIGNAL_VALLOX_STATE_UPDATE, self._update_callback
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Fetch state from the ventilation unit."""
        try:
            self._is_on = self._state_proxy.fetch_metric(self._metric_key)
            self._available = True

        except (OSError, KeyError) as err:
            self._available = False
            _LOGGER.error("Error updating sensor: %s", err)


class ValloxFilterOverdueBinarySensor(ValloxBinarySensor):
    """Child class for filter due signalling."""

    async def async_update(self):
        """Fetch state from the ventilation unit."""
        try:
            days_remaining = int(self._state_proxy.fetch_metric(self._metric_key))
            self._available = True

            if days_remaining == 0:
                self._is_on = True
            else:
                self._is_on = False

        except (OSError, KeyError) as err:
            self._available = False
            _LOGGER.error("Error updating sensor: %s", err)
