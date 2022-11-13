from homeassistant.components.light import *
from homeassistant.util import color

from .core.const import DOMAIN
from .core.entity import XEntity
from .core.ewelink import XRegistry, SIGNAL_ADD_ENTITIES

PARALLEL_UPDATES = 0  # fix entity_platform parallel_updates Semaphore


async def async_setup_entry(hass, config_entry, add_entities):
    ewelink: XRegistry = hass.data[DOMAIN][config_entry.entry_id]
    ewelink.dispatcher_connect(
        SIGNAL_ADD_ENTITIES,
        lambda x: add_entities([e for e in x if isinstance(e, LightEntity)])
    )


def conv(value: int, a1: int, a2: int, b1: int, b2: int) -> int:
    value = round((value - a1) / (a2 - a1) * (b2 - b1) + b1)
    if value < min(b1, b2):
        value = min(b1, b2)
    if value > max(b1, b2):
        value = max(b1, b2)
    return value


###############################################################################
# Category 1. XLight base (brightness)
###############################################################################

# https://developers.home-assistant.io/docs/core/entity/light/
# noinspection PyAbstractClass
class XLight(XEntity, LightEntity):
    uid = ""  # prevent add param to entity_id

    # support on/off and brightness
    _attr_color_mode = COLOR_MODE_BRIGHTNESS
    _attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}

    def set_state(self, params: dict):
        if self.param in params:
            self._attr_is_on = params[self.param] == 'on'

    def get_params(self, brightness, color_temp, rgb_color, effect) -> dict:
        pass

    async def async_turn_on(
            self, brightness: int = None, color_temp: int = None,
            rgb_color=None, xy_color=None, hs_color=None, effect: str = None,
            **kwargs
    ) -> None:
        if brightness == 0:
            await self.async_turn_off()
            return

        if xy_color:
            rgb_color = color.color_xy_to_RGB(*xy_color)
        elif hs_color:
            rgb_color = color.color_hs_to_RGB(*hs_color)

        if brightness or color_temp or rgb_color or effect:
            params = self.get_params(brightness, color_temp, rgb_color, effect)
        else:
            params = None

        if params:
            # some lights can only be turned on when the lights are off
            if not self.is_on:
                await self.ewelink.send(
                    self.device, {self.param: "on"}, query_cloud=False
                )
            await self.ewelink.send(
                self.device, params, {"cmd": "dimmable", **params}
            )
        else:
            await self.ewelink.send(self.device, {self.param: "on"})

    async def async_turn_off(self, **kwargs) -> None:
        await self.ewelink.send(self.device, {self.param: "off"})


# noinspection PyAbstractClass, UIID36
class XDimmer(XLight):
    params = {"switch", "bright"}
    param = "switch"

    def set_state(self, params: dict):
        XLight.set_state(self, params)
        if 'bright' in params:
            self._attr_brightness = conv(params['bright'], 10, 100, 1, 255)

    def get_params(self, brightness, color_temp, rgb_color, effect) -> dict:
        if brightness:
            return {"bright": conv(brightness, 1, 255, 10, 100)}


# noinspection PyAbstractClass, UIID57
class XLight57(XLight):
    params = {"state", "channel0"}
    param = "state"

    def set_state(self, params: dict):
        XLight.set_state(self, params)
        if 'channel0' in params:
            self._attr_brightness = conv(params['channel0'], 25, 255, 1, 255)

    def get_params(self, brightness, color_temp, rgb_color, effect) -> dict:
        if brightness:
            return {'channel0': str(conv(brightness, 1, 255, 25, 255))}


# noinspection PyAbstractClass, UIID44
class XLightD1(XLight):
    params = {"switch", "brightness"}
    param = "switch"

    def set_state(self, params: dict):
        XLight.set_state(self, params)
        if 'brightness' in params:
            self._attr_brightness = conv(params['brightness'], 0, 100, 1, 255)

    def get_params(self, brightness, color_temp, rgb_color, effect) -> dict:
        if brightness:
            # brightness can be only with switch=on in one message (error 400)
            # the purpose of the mode is unclear
            # max brightness=100 (error 400)
            return {
                "brightness": conv(brightness, 1, 255, 0, 100),
                "mode": 0, "switch": "on",
            }


###############################################################################
# Category 2. XLight base (color)
###############################################################################

UIID22_MODES = {
    "Good Night": {
        "channel0": "0", "channel1": "0", "channel2": "189", "channel3": "118",
        "channel4": "0", "zyx_mode": 3, "type": "middle"
    },
    "Reading": {
        "channel0": "0", "channel1": "0", "channel2": "255", "channel3": "255",
        "channel4": "255", "zyx_mode": 4, "type": "middle"
    },
    "Party": {
        "channel0": "0", "channel1": "0", "channel2": "207", "channel3": "56",
        "channel4": "3", "zyx_mode": 5, "type": "middle"
    },
    "Leisure": {
        "channel0": "0", "channel1": "0", "channel2": "56", "channel3": "85",
        "channel4": "179", "zyx_mode": 6, "type": "middle"
    }
}


# noinspection PyAbstractClass, UIID22
class XLightB1(XLight):
    params = {"state", "zyx_mode", "channel0", "channel2"}
    param = "state"

    _attr_min_mireds = 1  # cold
    _attr_max_mireds = 3  # warm
    _attr_effect_list = list(UIID22_MODES.keys())
    # support on/off, brightness, color_temp and RGB
    _attr_supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_RGB}
    _attr_supported_features = SUPPORT_EFFECT

    def set_state(self, params: dict):
        XLight.set_state(self, params)

        if 'zyx_mode' in params:
            mode = params["zyx_mode"]  # 1-6
            if mode == 1:
                self._attr_color_mode = COLOR_MODE_COLOR_TEMP
            else:
                self._attr_color_mode = COLOR_MODE_RGB
            if mode >= 3:
                self._attr_effect = self.effect_list[mode - 3]
            else:
                self._attr_effect = None

        if self.color_mode == COLOR_MODE_COLOR_TEMP:
            # from 25 to 255
            cold = int(params['channel0'])
            warm = int(params['channel1'])
            if warm == 0:
                self._attr_color_temp = 1
            elif cold == warm:
                self._attr_color_temp = 2
            elif cold == 0:
                self._attr_color_temp = 3
            self._attr_brightness = conv(max(cold, warm), 25, 255, 1, 255)

        else:
            self._attr_rgb_color = (
                int(params['channel2']), int(params['channel3']),
                int(params['channel4'])
            )

    def get_params(self, brightness, color_temp, rgb_color, effect) -> dict:
        if brightness or color_temp:
            ch = str(conv(brightness or self.brightness, 1, 255, 25, 255))
            if not color_temp:
                color_temp = self.color_temp
            if color_temp == 1:
                params = {"channel0": ch, "channel1": "0"}
            elif color_temp == 2:
                params = {"channel0": ch, "channel1": ch}
            elif color_temp == 3:
                params = {"channel0": ch, "channel1": ch}
            else:
                raise NotImplementedError

            return {
                **params, 'channel2': '0', 'channel3': '0', 'channel4': '0',
                'zyx_mode': 1
            }

        if rgb_color:
            return {
                'channel0': '0', 'channel1': '0',
                'channel2': str(rgb_color[0]), 'channel3': str(rgb_color[1]),
                'channel4': str(rgb_color[2]), 'zyx_mode': 2,
            }

        if effect:
            return UIID22_MODES[effect]


# noinspection PyAbstractClass, UIID59
class XLightL1(XLight):
    params = {"switch", "bright", "colorR", "mode"}
    param = "switch"

    _attr_color_mode = COLOR_MODE_RGB
    _attr_effect_list = [
        "Colorful", "Colorful Gradient", "Colorful Breath", "DIY Gradient", "DIY Pulse",
        "DIY Breath", "DIY Strobe", "RGB Gradient", "DIY Gradient",
        "RGB Breath", "RGB Strobe", "Music"
    ]
    # support on/off, brightness, RGB
    _attr_supported_color_modes = {COLOR_MODE_RGB}
    _attr_supported_features = SUPPORT_EFFECT

    def set_state(self, params: dict):
        XLight.set_state(self, params)

        if 'bright' in params:
            self._attr_brightness = conv(params['bright'], 1, 100, 1, 255)
        if 'colorR' in params and 'colorG' in params and 'colorB':
            self._attr_rgb_color = (
                params['colorR'], params['colorG'], params['colorB']
            )
        if 'mode' in params:
            mode = params['mode'] - 1  # 1=Colorful, don't skip it
            self._attr_effect = self.effect_list[mode] if mode >= 0 else None

    def get_params(self, brightness, color_temp, rgb_color, effect) -> dict:
        if effect:
            mode = self.effect_list.index(effect) + 1
            return {'mode': mode, "switch": "on"}
        if brightness or rgb_color:
            # support bright and color in one command
            params = {"mode": 1}
            if brightness:
                params["bright"] = conv(brightness, 1, 255, 1, 100)
            if rgb_color:
                params.update({
                    "colorR": rgb_color[0], "colorG": rgb_color[1],
                    "colorB": rgb_color[2], "light_type": 1
                })
            return params


B02_MODE_PAYLOADS = {
    "nightLight": {"br": 5, "ct": 0},
    "read": {"br": 50, "ct": 0},
    "computer": {"br": 20, "ct": 255},
    "bright": {"br": 100, "ct": 255},
}


# noinspection PyAbstractClass, UIID103
class XLightB02(XLight):
    params = {"switch", "ltype"}
    param = "switch"

    # FS-1, B02-F-A60 and other
    _attr_max_mireds: int = int(1000000 / 2200)  # 454
    _attr_min_mireds: int = int(1000000 / 6500)  # 153

    _attr_color_mode = COLOR_MODE_COLOR_TEMP
    _attr_effect_list = list(B02_MODE_PAYLOADS.keys())
    # support on/off, brightness and color_temp
    _attr_supported_color_modes = {COLOR_MODE_COLOR_TEMP}
    _attr_supported_features = SUPPORT_EFFECT

    def __init__(self, ewelink: XRegistry, device: dict):
        XEntity.__init__(self, ewelink, device)

        model = device.get("productModel")
        if model == "B02-F-ST64":
            self._attr_max_mireds = int(1000000 / 1800)  # 555
            self._attr_min_mireds = int(1000000 / 5000)  # 200
        elif model == "QMS-2C-CW":
            self._attr_max_mireds = int(1000000 / 2700)  # 370
            self._attr_min_mireds = int(1000000 / 6500)  # 153

    def set_state(self, params: dict):
        XLight.set_state(self, params)

        if "ltype" not in params:
            return

        self._attr_effect = params["ltype"]

        state = params[self.effect]
        if "br" in state:
            self._attr_brightness = conv(state["br"], 1, 100, 1, 255)
        if "ct" in state:
            self._attr_color_temp = conv(
                state["ct"], 0, 255, self.max_mireds, self.min_mireds
            )

    def get_params(self, brightness, color_temp, rgb_color, effect) -> dict:
        if brightness or color_temp:
            return {
                "ltype": "white",
                "white": {
                    "br": conv(brightness or self.brightness, 1, 255, 1, 100),
                    "ct": conv(
                        color_temp or self.color_temp, self.max_mireds,
                        self.min_mireds, 0, 255
                    )
                }
            }
        if effect:
            return {"ltype": effect, effect: B02_MODE_PAYLOADS[effect]}


# Taken straight from the debug mode and the eWeLink app
B05_MODE_PAYLOADS = {
    'bright': {'r': 255, 'g': 255, 'b': 255, 'br': 100},
    'goodNight': {'r': 254, 'g': 254, 'b': 126, 'br': 25},
    'read': {'r': 255, 'g': 255, 'b': 255, 'br': 60},
    'nightLight': {'r': 255, 'g': 242, 'b': 226, 'br': 5},
    'party': {'r': 254, 'g': 132, 'b': 0, 'br': 45, 'tf': 1, 'sp': 1},
    'leisure': {'r': 0, 'g': 40, 'b': 254, 'br': 55, 'tf': 1, 'sp': 1},
    'soft': {'r': 38, 'g': 254, 'b': 0, 'br': 20, 'tf': 1, 'sp': 1},
    'colorful': {'r': 255, 'g': 0, 'b': 0, 'br': 100, 'tf': 1, 'sp': 1},
}


# noinspection PyAbstractClass, UIID 104
class XLightB05B(XLightB02):
    _attr_effect_list = list(B05_MODE_PAYLOADS.keys())
    # support on/off, brightness, color_temp and RGB
    _attr_supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_RGB}
    _attr_max_mireds = 500
    _attr_min_mireds = 153

    def set_state(self, params: dict):
        XLight.set_state(self, params)

        if "ltype" not in params:
            return

        effect = params["ltype"]
        if effect == "white":
            self._attr_color_mode = COLOR_MODE_COLOR_TEMP
        else:
            self._attr_color_mode = COLOR_MODE_RGB

        if effect in self.effect_list:
            self._attr_effect = effect

        state = params[effect]
        if "br" in state:
            self._attr_brightness = conv(state["br"], 1, 100, 1, 255)

        if "ct" in state:
            self._attr_color_temp = conv(
                state["ct"], 0, 255, self.max_mireds, self.min_mireds
            )

        if 'r' in state or 'g' in state or 'b' in state:
            self._attr_rgb_color = (
                state.get('r', 0), state.get('g', 0), state.get('b', 0)
            )

    def get_params(self, brightness, color_temp, rgb_color, effect) -> dict:
        if color_temp:
            return {
                "ltype": "white",
                "white": {
                    'br': conv(brightness or self.brightness, 1, 255, 1, 100),
                    'ct': conv(
                        color_temp, self.max_mireds, self.min_mireds, 0, 255
                    )
                }
            }
        if rgb_color:
            return {
                "ltype": "color",
                "color": {
                    'br': conv(brightness or self.brightness, 1, 255, 1, 100),
                    'r': rgb_color[0], 'g': rgb_color[1], 'b': rgb_color[2],
                }
            }
        if brightness:
            if self.color_mode == COLOR_MODE_COLOR_TEMP:
                return self.get_params(brightness, self.color_temp, None, None)
            else:
                return self.get_params(brightness, None, self.rgb_color, None)
        if effect is not None:
            return {"ltype": effect, effect: B05_MODE_PAYLOADS[effect]}


###############################################################################
# Category 3. Other
###############################################################################

# noinspection PyAbstractClass
class XLightGroup(XEntity, LightEntity):
    """Differs from the usual switch by brightness adjustment. Is logical
    use only for two or more channels. Able to remember brightness on moment
    off.
    The sequence of channels is important. The first channels will be turned on
    at low brightness.
    """
    params = {"switches"}
    channels: list = None

    _attr_brightness = 0
    # support on/off and brightness
    _attr_color_mode = COLOR_MODE_BRIGHTNESS
    _attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}

    def set_state(self, params: dict):
        cnt = sum(
            1 for i in params["switches"]
            if i["outlet"] in self.channels and i["switch"] == "on"
        )
        if cnt:
            # if at least something is on - remember the new brightness
            self._attr_brightness = round(cnt / len(self.channels) * 255)
            self._attr_is_on = True
        else:
            self._attr_is_on = False

    async def async_turn_on(self, brightness: int = None, **kwargs):
        if brightness is not None:
            self._attr_brightness = brightness
        elif self._attr_brightness == 0:
            self._attr_brightness = 255

        # how much light should turn on at such brightness
        cnt = round(self._attr_brightness / 255 * len(self.channels))

        # the first part of the lights - turn on, the second - turn off
        switches = [
            {"outlet": channel, "switch": "on" if i < cnt else "off"}
            for i, channel in enumerate(self.channels)
        ]
        await self.ewelink.send_bulk(self.device, {"switches": switches})

    async def async_turn_off(self, **kwargs) -> None:
        switches = [{"outlet": ch, "switch": "off"} for ch in self.channels]
        await self.ewelink.send_bulk(self.device, {"switches": switches})


# noinspection PyAbstractClass, UIID22
class XFanLight(XEntity, LightEntity):
    params = {"switches", "light"}
    uid = "1"  # backward compatibility

    def set_state(self, params: dict):
        if "switches" in params:
            params = next(i for i in params["switches"] if i["outlet"] == 0)
            self._attr_is_on = params["switch"] == "on"
        else:
            self._attr_is_on = params["light"] == "on"

    async def async_turn_on(self, **kwargs):
        params = {"switches": [{"outlet": 0, "switch": "on"}]}
        if self.device.get("localtype") == "fan_light":
            params_lan = {"light": "on"}
        else:
            params_lan = None
        await self.ewelink.send(self.device, params, params_lan)

    async def async_turn_off(self):
        params = {"switches": [{"outlet": 0, "switch": "off"}]}
        if self.device.get("localtype") == "fan_light":
            params_lan = {"light": "off"}
        else:
            params_lan = None
        await self.ewelink.send(self.device, params, params_lan)


# noinspection PyAbstractClass, UIID25
class XDiffuserLight(XEntity, LightEntity):
    params = {"lightswitch", "lightbright", "lightmode", "lightRcolor"}

    _attr_effect_list = ["Color Light", "RGB Color", "Night Light"]
    _attr_supported_features = SUPPORT_EFFECT

    def set_state(self, params: dict):
        if 'lightswitch' in params:
            self._attr_is_on = params['lightswitch'] == 1

        if 'lightbright' in params:
            self._attr_brightness = conv(params['lightbright'], 0, 100, 1, 255)

        if 'lightmode' in params:
            mode = params['lightmode']
            if mode == 1:
                # support on/off
                self._attr_color_mode = COLOR_MODE_ONOFF
                self._attr_supported_color_modes = {COLOR_MODE_ONOFF}
            elif mode == 2:
                self._attr_color_mode = COLOR_MODE_RGB
                # support on/off, brightness and RGB
                self._attr_supported_color_modes = {COLOR_MODE_RGB}
            elif mode == 3:
                # support on/off and brightness
                self._attr_color_mode = COLOR_MODE_BRIGHTNESS
                self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}

        if 'lightRcolor' in params:
            self._attr_rgb_color = (
                params['lightRcolor'], params['lightGcolor'],
                params['lightBcolor']
            )

    async def async_turn_on(
            self, brightness: int = None, rgb_color=None, effect: str = None,
            **kwargs
    ) -> None:
        params = {}

        if effect is not None:
            params['lightmode'] = mode = self.effect.index(effect) + 1
            if mode == 2 and rgb_color is None:
                rgb_color = self._attr_rgb_color

        if brightness is not None:
            params['lightbright'] = conv(brightness, 1, 255, 0, 100)

        if rgb_color is not None:
            params.update({
                'lightmode': 2, 'lightRcolor': rgb_color[0],
                'lightGcolor': rgb_color[1], 'lightBcolor': rgb_color[2]
            })

        if not params:
            params['lightswitch'] = 1

        await self.ewelink.send(self.device, params)

    async def async_turn_off(self, **kwargs) -> None:
        await self.ewelink.send(self.device, {'lightswitch': 0})
