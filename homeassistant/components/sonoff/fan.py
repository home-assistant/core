from homeassistant.components.fan import FanEntity, SUPPORT_SET_SPEED, \
    SUPPORT_PRESET_MODE

from .core.const import DOMAIN
from .core.entity import XEntity
from .core.ewelink import XRegistry, SIGNAL_ADD_ENTITIES

PARALLEL_UPDATES = 0  # fix entity_platform parallel_updates Semaphore


async def async_setup_entry(hass, config_entry, add_entities):
    ewelink: XRegistry = hass.data[DOMAIN][config_entry.entry_id]
    ewelink.dispatcher_connect(
        SIGNAL_ADD_ENTITIES,
        lambda x: add_entities([e for e in x if isinstance(e, FanEntity)])
    )


SPEED_OFF = "off"
SPEED_LOW = "low"
SPEED_MEDIUM = "medium"
SPEED_HIGH = "high"


# noinspection PyAbstractClass
class XFan(XEntity, FanEntity):
    params = {"switches", "fan"}
    _attr_speed_count = 3
    _attr_supported_features = SUPPORT_SET_SPEED | SUPPORT_PRESET_MODE
    _attr_preset_modes = [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def set_state(self, params: dict):
        mode = None
        # Cloud sends switches, LAN sends fan/speed
        if "switches" in params:
            s = {i["outlet"]: i["switch"] for i in params["switches"]}
            if s[1] == "off":
                pass
            elif s[2] == "off" and s[3] == "off":
                mode = SPEED_LOW
            elif s[2] == "on" and s[3] == "off":
                mode = SPEED_MEDIUM
            elif s[2] == "off" and s[3] == "on":
                mode = SPEED_HIGH
        else:
            if params["fan"] == "off":
                pass
            elif params["speed"] == 1:
                mode = SPEED_LOW
            elif params["speed"] == 2:
                mode = SPEED_MEDIUM
            elif params["speed"] == 3:
                mode = SPEED_HIGH

        self._attr_percentage = int(
            self._attr_preset_modes.index(mode or SPEED_OFF) /
            self._attr_speed_count * 100
        )
        self._attr_preset_mode = mode

    async def async_set_percentage(self, percentage: int):
        if percentage is None:
            param = {1: "on"}
            params_lan = {"fan": "on"}
        elif percentage > 66:
            param = {1: "on", 2: "off", 3: "on"}  # high
            params_lan = {"fan": "on", "speed": 3}
        elif percentage > 33:
            param = {1: "on", 2: "on", 3: "off"}  # medium
            params_lan = {"fan": "on", "speed": 2}
        elif percentage > 0:
            param = {1: "on", 2: "off", 3: "off"}  # low
            params_lan = {"fan": "on", "speed": 1}
        else:
            param = {1: "off"}
            params_lan = {"fan": "off"}
        param = [{"outlet": k, "switch": v} for k, v in param.items()]
        # fan_light - iFan03 and iFan04 using new LAN API
        # strip - iFan02 using old LAN API (same as cloud)
        if self.device.get("localtype") != "fan_light":
            params_lan = None
        await self.ewelink.send(self.device, {"switches": param}, params_lan)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        percentage = int(
            self._attr_preset_modes.index(preset_mode) /
            self._attr_speed_count * 100
        )
        await self.async_set_percentage(percentage)

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        else:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self):
        await self.async_set_percentage(0)


# noinspection PyAbstractClass
class XDiffuserFan(XFan):
    params = {"state", "switch"}
    _attr_speed_count = 2
    _attr_preset_modes = [SPEED_OFF, SPEED_LOW, SPEED_HIGH]

    def set_state(self, params: dict):
        if params["switch"] == "off":
            self._attr_percentage = 0
            self._attr_preset_mode = None
        elif params["state"] == 1:
            self._attr_percentage = 50
            self._attr_preset_mode = SPEED_LOW
        elif params["state"] == 2:
            self._attr_percentage = 100
            self._attr_preset_mode = SPEED_HIGH

    async def async_set_percentage(self, percentage: int):
        if percentage is None:
            param = {"switch": "on"}
        elif percentage > 50:
            param = {"switch": "on", "state": 2}
        elif percentage > 0:
            param = {"switch": "on", "state": 1}
        else:
            param = {"switch": "off"}
        await self.ewelink.send(self.device, param)


# noinspection PyAbstractClass
class XToggleFan(XEntity, FanEntity):
    @property
    def is_on(self):
        return self._attr_is_on
