"""Support for Exta Life on/off switches: ROP, ROM, ROG devices"""
import logging
from pprint import pformat

from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import ExtaLifeChannel
from .helpers.const import DOMAIN
from .helpers.core import Core
from .pyextalife import MODEL_ROG21, ExtaLifeAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """setup via configuration.yaml not supported anymore"""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up Exta Life switches based on existing config."""

    core = Core.get(config_entry.entry_id)
    channels = core.get_channels(DOMAIN_SWITCH)

    _LOGGER.debug("Discovery: %s", pformat(channels))
    async_add_entities([ExtaLifeSwitch(device, config_entry) for device in channels])

    core.pop_channels(DOMAIN_SWITCH)


class ExtaLifeSwitch(ExtaLifeChannel, SwitchEntity):
    """Representation of an ExtaLife Switch."""

    def __init__(self, channel_data, config_entry):
        super().__init__(channel_data, config_entry)
        self.channel_data = channel_data.get("data")

        data = self.channel_data

        self._type = data.get("type")

        self._assumed_on = False

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        if not self.is_exta_free:
            if await self.async_action(ExtaLifeAPI.ACTN_TURN_ON):
                field = (
                    "power"
                    if self.channel_data.get("output_state") is None
                    else "output_state"
                )
                self.channel_data[field] = 1
                self.async_schedule_update_ha_state()
        else:
            if await self.async_action(
                ExtaLifeAPI.ACTN_EXFREE_TURN_ON_PRESS
            ) and await self.async_action(ExtaLifeAPI.ACTN_EXFREE_TURN_ON_RELEASE):
                self._assumed_on = True
                self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        if not self.is_exta_free:
            if await self.async_action(ExtaLifeAPI.ACTN_TURN_OFF):
                field = (
                    "power"
                    if self.channel_data.get("output_state") is None
                    else "output_state"
                )
                self.channel_data[field] = 0
                self.async_schedule_update_ha_state()
        else:
            if await self.async_action(
                ExtaLifeAPI.ACTN_EXFREE_TURN_OFF_PRESS
            ) and await self.async_action(ExtaLifeAPI.ACTN_EXFREE_TURN_OFF_RELEASE):
                self._assumed_on = False
                self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self.is_exta_free:
            return self._assumed_on

        field = (
            "power" if self.channel_data.get("output_state") is None else "output_state"
        )
        state = self.channel_data.get(field)

        if state == 1 or state == True:
            return True
        return False

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = super().device_state_attributes
        data = self.channel_data

        # ROG-21 measurement attributes
        if self.model == MODEL_ROG21:
            attr.update(
                {
                    "voltage": data.get("voltage") / 100,
                    "current": data.get("current") / 1000,
                    "active_power": data.get("active_power"),
                    "energy_consumption": data.get("manual_energy") / 100000,
                }
            )

        return attr

    def on_state_notification(self, data):
        """ React on state notification from controller """

        state = data.get("state")
        ch_data = self.channel_data.copy()

        if ch_data.get("power") is not None:
            ch_data["power"] = 1 if state else 0
        elif ch_data.get("output_state") is not None:
            ch_data["output_state"] = state

        # update only if notification data contains new status; prevent HA event bus overloading
        if ch_data != self.channel_data:
            self.channel_data.update(ch_data)

            # synchronize DataManager data with processed update & entity data
            self.sync_data_update_ha()
