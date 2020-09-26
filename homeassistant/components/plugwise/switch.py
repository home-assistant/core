"""Plugwise Switch component for HomeAssistant."""

import logging

from Plugwise_Smile.Smile import Smile

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from . import SmileGateway
from .const import COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile switches from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    all_devices = api.get_all_devices()
    for dev_id, device_properties in all_devices.items():
        if "plug" in device_properties["types"]:
            model = "Metered Switch"
            entities.append(
                PwSwitch(api, coordinator, device_properties["name"], dev_id, model)
            )

    async_add_entities(entities, True)


class PwSwitch(SmileGateway, SwitchEntity):
    """Representation of a Plugwise plug."""

    def __init__(self, api, coordinator, name, dev_id, model):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id)

        self._model = model

        self._is_on = False

        self._unique_id = f"{dev_id}-plug"

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            if await self._api.set_relay_state(self._dev_id, "on"):
                self._is_on = True
                self.async_write_ha_state()
        except Smile.PlugwiseError:
            _LOGGER.error("Error while communicating to device")

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        try:
            if await self._api.set_relay_state(self._dev_id, "off"):
                self._is_on = False
                self.async_write_ha_state()
        except Smile.PlugwiseError:
            _LOGGER.error("Error while communicating to device")

    @callback
    def _async_process_data(self):
        """Update the data from the Plugs."""
        _LOGGER.debug("Update switch called")

        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s", self._name)
            self.async_write_ha_state()
            return

        if "relay" in data:
            self._is_on = data["relay"]

        self.async_write_ha_state()
