"""Plugwise Switch component for HomeAssistant."""

import logging

from plugwise.exceptions import PlugwiseException

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from .const import COORDINATOR, DOMAIN, SWITCH_ICON
from .gateway import SmileGateway

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile switches from a config entry."""
    # PLACEHOLDER USB entry setup
    return await async_setup_entry_gateway(hass, config_entry, async_add_entities)


async def async_setup_entry_gateway(hass, config_entry, async_add_entities):
    """Set up the Smile switches from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    switch_classes = ["plug", "switch_group"]

    all_devices = api.get_all_devices()
    for dev_id, device_properties in all_devices.items():
        members = None
        model = None

        if any(
            switch_class in device_properties["types"]
            for switch_class in switch_classes
        ):
            if "plug" in device_properties["types"]:
                model = "Metered Switch"
            if "switch_group" in device_properties["types"]:
                members = device_properties["members"]
                model = "Switch Group"

            entities.append(
                GwSwitch(
                    api, coordinator, device_properties["name"], dev_id, members, model
                )
            )

    async_add_entities(entities, True)


class GwSwitch(SmileGateway, SwitchEntity):
    """Representation of a Plugwise plug."""

    def __init__(self, api, coordinator, name, dev_id, members, model):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id)

        self._members = members
        self._model = model

        self._is_on = False
        self._icon = SWITCH_ICON

        self._unique_id = f"{dev_id}-plug"

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

    @property
    def icon(self):
        """Return the icon of this entity."""
        return self._icon

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            state_on = await self._api.set_relay_state(
                self._dev_id, self._members, "on"
            )
            if state_on:
                self._is_on = True
                self.async_write_ha_state()
        except PlugwiseException:
            _LOGGER.error("Error while communicating to device")

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        try:
            state_off = await self._api.set_relay_state(
                self._dev_id, self._members, "off"
            )
            if state_off:
                self._is_on = False
                self.async_write_ha_state()
        except PlugwiseException:
            _LOGGER.error("Error while communicating to device")

    @callback
    def _async_process_data(self):
        """Update the data from the Plugs."""
        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s", self._name)
            self.async_write_ha_state()
            return

        if "relay" in data:
            self._is_on = data["relay"]

        self.async_write_ha_state()
