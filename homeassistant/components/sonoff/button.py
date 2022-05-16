from homeassistant.components.button import ButtonEntity
from homeassistant.components.script import ATTR_LAST_TRIGGERED
from homeassistant.helpers.entity import DeviceInfo

from .core.const import DOMAIN
from .core.ewelink import XRegistry, SIGNAL_ADD_ENTITIES

PARALLEL_UPDATES = 0  # fix entity_platform parallel_updates Semaphore


async def async_setup_entry(hass, config_entry, add_entities):
    ewelink: XRegistry = hass.data[DOMAIN][config_entry.entry_id]
    ewelink.dispatcher_connect(
        SIGNAL_ADD_ENTITIES,
        lambda x: add_entities([e for e in x if isinstance(e, ButtonEntity)])
    )


# supported in Hass v2021.12
# noinspection PyAbstractClass
class XRemoteButton(ButtonEntity):
    def __init__(self, ewelink: XRegistry, bridge: dict, child: dict):
        self.ewelink = ewelink
        self.bridge = bridge
        self.channel = child["channel"]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bridge["deviceid"])}
        )
        self._attr_extra_state_attributes = {}
        self._attr_name = child["name"]
        self._attr_unique_id = f"{bridge['deviceid']}_{self.channel}"

        self.entity_id = DOMAIN + "." + self._attr_unique_id

    def internal_update(self, ts: str):
        self._attr_extra_state_attributes = {ATTR_LAST_TRIGGERED: ts}
        self._async_write_ha_state()

    async def async_press(self):
        await self.ewelink.send(self.bridge, {
            "cmd": "transmit", "rfChl": int(self.channel)
        })
