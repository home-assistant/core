"""Plugwise Switch component for HomeAssistant."""
from __future__ import annotations

import logging

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    ATTR_ID,
    ATTR_NAME,
    ATTR_STATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback

from plugwise.exceptions import PlugwiseException
from plugwise.nodes import PlugwiseNode

from .const import (
    API,
    CB_NEW_NODE,
    COORDINATOR,
    DOMAIN,
    FW,
    PW_MODEL,
    PW_TYPE,
    SMILE,
    STICK,
    USB,
    VENDOR,
)
from .gateway import SmileGateway
from .models import PW_SWITCH_TYPES, PlugwiseSwitchEntityDescription
from .usb import PlugwiseUSBEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile switches from a config entry."""
    # PLACEHOLDER for async_setup_entry_usb()
    return await async_setup_entry_gateway(hass, config_entry, async_add_entities)

async def async_setup_entry_gateway(hass, config_entry, async_add_entities):
    """Set up the Smile switches from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id][API]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    for dev_id in coordinator.data[1]:
        for key in coordinator.data[1][dev_id]:
            if key != "switches":
                continue

            for data in coordinator.data[1][dev_id]["switches"]:
                for description in PW_SWITCH_TYPES:
                    if (
                        description.plugwise_api == SMILE
                        and description.key == data.get(ATTR_ID)
                    ):
                        entities.extend(
                            [
                                GwSwitch(
                                    api,
                                    coordinator,
                                    description,
                                    dev_id,
                                    data,
                                )
                            ]
                        )

    if entities:
        async_add_entities(entities, True)


class GwSwitch(SmileGateway, SwitchEntity):
    """Representation of a Smile Gateway switch."""

    def __init__(
        self,
        api,
        coordinator,
        description: PlugwiseSwitchEntityDescription,
        dev_id,
        sw_data,
    ):
        """Initialise the sensor."""
        _cdata = coordinator.data[1][dev_id]
        super().__init__(
            coordinator,
            description,
            dev_id,
            _cdata.get(PW_MODEL),
            _cdata.get(ATTR_NAME),
            _cdata.get(VENDOR),
            _cdata.get(FW),
        )

        self._api = api
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        self._attr_icon = description.icon
        self._attr_is_on = False
        self._attr_name = f"{_cdata.get(ATTR_NAME)} {description.name}"
        self._attr_should_poll = self.entity_description.should_poll
        self._dev_id = dev_id
        self._members = None
        if "members" in coordinator.data[1][dev_id]:
            self._members = coordinator.data[1][dev_id].get("members")
        self._switch = description.key
        self._sw_data = sw_data

        self._attr_unique_id = f"{dev_id}-{description.key}"
        # For backwards compatibility:
        if self._switch == "relay":
            self._attr_unique_id = f"{dev_id}-plug"
            self._attr_name = _cdata.get(ATTR_NAME)

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            state_on = await self._api.set_switch_state(
                self._dev_id, self._members, self._switch, STATE_ON
            )
            if state_on:
                self._attr_is_on = True
                self.async_write_ha_state()
                _LOGGER.debug("Turn Plugwise switch.%s on", self._attr_name)
        except PlugwiseException:
            _LOGGER.error("Error: failed to turn Plugwise switch.%s on", self._attr_name)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        try:
            state_off = await self._api.set_switch_state(
                self._dev_id, self._members, self._switch, STATE_OFF
            )
            if state_off:
                self._attr_is_on = False
                self.async_write_ha_state()
                _LOGGER.debug("Turn Plugwise switch.%s on", self._attr_name)
        except PlugwiseException:
            _LOGGER.error("Error: failed to turn Plugwise switch.%s off", self._attr_name)

    @callback
    def _async_process_data(self):
        """Update the data from the Plugs."""
        self._attr_is_on = self._sw_data.get(ATTR_STATE)
        self.async_write_ha_state()


# PLACEHOLDER for class USBSwitch():
