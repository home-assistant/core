""" Integration microBees """

import logging
from homeassistant.components.switch import ToggleEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .servicesMicrobees import sendCommand

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    token = dict(entry.data)["token"]

    bees = dict(entry.data)["bees"]

    switches = []
    for bee in bees:
        if bee.get("active"):
            if bee.get("productID") == 46:
                for switch in bee.get("actuators"):
                    switches.append(MBSwitch(switch, token))

    async_add_entities(switches)


class MBSwitch(ToggleEntity):
    def __init__(self, act, token):
        self.act = act
        self.token = token
        self._state = self.act.get("value")
        self.async_update()

    @property
    def name(self):
        return self.act.get("name")

    @property
    def unique_id(self):
        return self.act.get("id")

    @property
    def is_on(self):
        return self.act.get("value")

    async def async_turn_on(self, **kwargs):
        _LOGGER.info("switch turn_on")
        data = {
            "actuatorID": self.act.get("id"),
            "command_type": 6,
            "data": {
                "actuatorID": self.act.get("id"),
                "command_type": 6,
                "relay_value": 1,
            },
        }
        await sendCommand(self.token, data)
        self.act["value"] = 1

    async def async_turn_off(self, **kwargs):
        _LOGGER.info("switch turn_off")
        data = {
            "actuatorID": self.act.get("id"),
            "command_type": 6,
            "data": {
                "actuatorID": self.act.get("id"),
                "command_type": 6,
                "relay_value": 0,
            },
        }
        await sendCommand(self.token, data)
        self.act["value"] = 0

    async def async_update(self):
        self._state = self.act.get("value")
