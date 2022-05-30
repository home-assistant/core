from homeassistant.components.cover import CoverEntity, CoverDeviceClass

from .core.const import DOMAIN
from .core.entity import XEntity
from .core.ewelink import XRegistry, SIGNAL_ADD_ENTITIES

PARALLEL_UPDATES = 0  # fix entity_platform parallel_updates Semaphore


async def async_setup_entry(hass, config_entry, add_entities):
    ewelink: XRegistry = hass.data[DOMAIN][config_entry.entry_id]
    ewelink.dispatcher_connect(
        SIGNAL_ADD_ENTITIES,
        lambda x: add_entities([e for e in x if isinstance(e, CoverEntity)])
    )


# noinspection PyUnresolvedReferences
DEVICE_CLASSES = {cls.value: cls for cls in CoverDeviceClass}


# noinspection PyAbstractClass
class XCover(XEntity, CoverEntity):
    params = {"switch", "setclose"}

    def __init__(self, ewelink: XRegistry, device: dict):
        XEntity.__init__(self, ewelink, device)
        self._attr_device_class = DEVICE_CLASSES.get(
            device.get("device_class")
        )

    def set_state(self, params: dict):
        # => command to cover from mobile app
        if len(params) == 1:
            if "switch" in params:
                # device receive command - on=open/off=close/pause=stop
                self._attr_is_opening = params["switch"] == "on"
                self._attr_is_closing = params["switch"] == "off"
            elif "setclose" in params:
                # device receive command - mode to position
                pos = 100 - params["setclose"]
                self._attr_is_closing = pos < self.current_cover_position
                self._attr_is_opening = pos > self.current_cover_position

        # BINTHEN BCM Series payload:
        #   {"sequence":"1652428259464","setclose":38}
        # KingArt KING-Q4 payloads:
        #   {"switch":"off","setclose":21} or {"switch":"on","setclose":0}
        elif "setclose" in params:
            # the device has finished the action
            # reversed position: HA closed at 0, eWeLink closed at 100
            self._attr_current_cover_position = 100 - params["setclose"]
            self._attr_is_closed = self.current_cover_position == 0
            self._attr_is_closing = False
            self._attr_is_opening = False

    async def async_stop_cover(self, **kwargs):
        params = {"switch": "pause"}
        self.set_state(params)
        self._async_write_ha_state()
        await self.ewelink.send(self.device, params, query_cloud=False)

    async def async_open_cover(self, **kwargs):
        params = {"switch": "on"}
        self.set_state(params)
        self._async_write_ha_state()
        await self.ewelink.send(self.device, params, query_cloud=False)

    async def async_close_cover(self, **kwargs):
        params = {"switch": "off"}
        self.set_state(params)
        self._async_write_ha_state()
        await self.ewelink.send(self.device, params, query_cloud=False)

    async def async_set_cover_position(self, position: int, **kwargs):
        params = {"setclose": 100 - position}
        self.set_state(params)
        self._async_write_ha_state()
        await self.ewelink.send(self.device, params, query_cloud=False)


# noinspection PyAbstractClass
class XCoverDualR3(XCover):
    params = {"currLocation", "motorTurn"}

    def set_state(self, params: dict):
        if "currLocation" in params:
            # 0 - closed, 100 - opened
            self._attr_current_cover_position = params["currLocation"]
            self._attr_is_closed = self._attr_current_cover_position == 0

        if "motorTurn" in params:
            if params["motorTurn"] == 0:  # stop
                self._attr_is_opening = False
                self._attr_is_closing = False
            elif params["motorTurn"] == 1:
                self._attr_is_opening = True
                self._attr_is_closing = False
            elif params["motorTurn"] == 2:
                self._attr_is_opening = False
                self._attr_is_closing = True

    async def async_stop_cover(self, **kwargs):
        await self.ewelink.send(self.device, {"motorTurn": 0})

    async def async_open_cover(self, **kwargs):
        await self.ewelink.send(self.device, {"motorTurn": 1})

    async def async_close_cover(self, **kwargs):
        await self.ewelink.send(self.device, {"motorTurn": 2})

    async def async_set_cover_position(self, position: int, **kwargs):
        await self.ewelink.send(self.device, {"location": position})
