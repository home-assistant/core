"""
Firmware   | LAN type  | uiid | Product Model
-----------|-----------|------|--------------
PSF-BLD-GL | light     | 44   | D1 (Sonoff D1)
PSF-BFB-GL | fan_light | 34   | iFan (Sonoff iFan03)
"""
import logging

from homeassistant.components.light import SUPPORT_BRIGHTNESS, \
    ATTR_BRIGHTNESS, SUPPORT_COLOR, ATTR_HS_COLOR, \
    SUPPORT_EFFECT, ATTR_EFFECT, ATTR_EFFECT_LIST, SUPPORT_COLOR_TEMP, \
    ATTR_COLOR_TEMP, ATTR_MIN_MIREDS, ATTR_MAX_MIREDS
from homeassistant.util import color

# noinspection PyUnresolvedReferences
from . import DOMAIN, SCAN_INTERVAL
from .switch import EWeLinkToggle

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    if discovery_info is None:
        return

    deviceid = discovery_info['deviceid']
    channels = discovery_info['channels']
    registry = hass.data[DOMAIN]
    device = registry.devices[deviceid]

    uiid = device.get('uiid')
    if uiid == 44 or uiid == 'light':
        add_entities([SonoffD1(registry, deviceid)])
    elif uiid == 59:
        add_entities([SonoffLED(registry, deviceid)])
    elif uiid == 22:
        add_entities([SonoffB1(registry, deviceid)])
    elif uiid == 36:
        add_entities([SonoffDimmer(registry, deviceid)])
    elif uiid == 25:
        add_entities([SonoffDiffuserLight(registry, deviceid)])
    elif channels and len(channels) >= 2:
        add_entities([EWeLinkLightGroup(registry, deviceid, channels)])
    else:
        add_entities([EWeLinkToggle(registry, deviceid, channels)])


class SonoffD1(EWeLinkToggle):
    _brightness = 0

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        if 'brightness' in state:
            self._brightness = max(round(state['brightness'] * 2.55), 1)

        if 'switch' in state:
            self._is_on = state['switch'] == 'on'

        self.schedule_update_ha_state()

    @property
    def brightness(self):
        return self._brightness

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS

    @property
    def state_attributes(self):
        return {
            **self._attrs,
            ATTR_BRIGHTNESS: self.brightness
        }

    async def async_turn_on(self, **kwargs) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        br = max(round(self._brightness / 2.55), 1)
        # cmd param only for local mode, no need for cloud
        await self.registry.send(self.deviceid, {
            'cmd': 'dimmable', 'switch': 'on', 'brightness': br, 'mode': 0})


class SonoffDimmer(SonoffD1):
    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        # if 'online' in state:
        #     self._available = state['online']

        if 'bright' in state:
            # from 10 to 100 => 1 .. 255
            br = round((state['bright'] - 10) / (100 - 10) * 255)
            self._brightness = max(br, 1)

        if 'switch' in state:
            self._is_on = state['switch'] == 'on'

        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        br = 10 + round(self._brightness / 255 * (100 - 10))
        await self.registry.send(self.deviceid, {'switch': 'on', 'bright': br})


LED_EFFECTS = [
    "Colorful", "Colorful Gradient", "Colorful Breath", "DIY Gradient",
    "DIY Pulse", "DIY Breath", "DIY Strobe", "RGB Gradient", "DIY Gradient",
    "RGB Breath", "RGB Strobe", "Music"
]


class SonoffLED(EWeLinkToggle):
    _brightness = 0
    _hs_color = None
    _mode = 0

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        # if 'online' in state:
        #     self._available = state['online']

        if 'bright' in state:
            # sonoff brightness from 1 to 100
            self._brightness = max(round(state['bright'] * 2.55), 1)

        if 'colorR' in state and 'colorG' in state and 'colorB':
            self._hs_color = color.color_RGB_to_hs(
                state['colorR'], state['colorG'], state['colorB'])

        if 'mode' in state:
            self._mode = state['mode'] - 1

        if 'switch' in state:
            self._is_on = state['switch'] == 'on'

        self.schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return self._hs_color

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return LED_EFFECTS

    @property
    def effect(self):
        """Return the current effect."""
        return LED_EFFECTS[self._mode]

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_EFFECT

    @property
    def state_attributes(self):
        return {
            **self._attrs,
            ATTR_BRIGHTNESS: self.brightness,
            ATTR_HS_COLOR: self._hs_color,
            ATTR_EFFECT: self.effect
        }

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        return {ATTR_EFFECT_LIST: self.effect_list}

    async def async_turn_on(self, **kwargs) -> None:
        if ATTR_EFFECT in kwargs:
            mode = LED_EFFECTS.index(kwargs[ATTR_EFFECT]) + 1
            payload = {'switch': 'on', 'mode': mode}

        elif ATTR_BRIGHTNESS in kwargs or ATTR_HS_COLOR in kwargs:
            payload = {'mode': 1}

            if ATTR_BRIGHTNESS in kwargs:
                br = max(round(kwargs[ATTR_BRIGHTNESS] / 2.55), 1)
                payload['bright'] = br

            if ATTR_HS_COLOR in kwargs:
                rgb = color.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
                payload.update({'colorR': rgb[0], 'colorG': rgb[1],
                                'colorB': rgb[2], 'light_type': 1})

        else:
            payload = {'switch': 'on'}

        await self.registry.send(self.deviceid, payload)


class SonoffB1(EWeLinkToggle):
    _brightness = None
    _hs_color = None
    _temp = None

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        if 'zyx_mode' in state:
            mode = state['zyx_mode']
        elif 'channel0' in state:
            mode = 1
        elif 'channel2' in state:
            mode = 2
        else:
            mode = None

        if mode == 1:
            # from 25 to 255
            cold = int(state['channel0'])
            warm = int(state['channel1'])
            if warm == 0:
                self._temp = 1
            elif cold == warm:
                self._temp = 2
            elif cold == 0:
                self._temp = 3
            br = round((max(cold, warm) - 25) / (255 - 25) * 255)
            # from 1 to 100
            self._brightness = max(br, 1)
            self._hs_color = None

        elif mode == 2:
            self._hs_color = color.color_RGB_to_hs(
                int(state['channel2']),
                int(state['channel3']),
                int(state['channel4'])
            )

        if 'state' in state:
            self._is_on = state['state'] == 'on'

        self.schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return self._hs_color

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._temp

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP

    @property
    def capability_attributes(self):
        return {
            ATTR_MIN_MIREDS: 1,
            ATTR_MAX_MIREDS: 3
        }

    @property
    def state_attributes(self):
        return {
            **self._attrs,
            ATTR_BRIGHTNESS: self.brightness,
            ATTR_HS_COLOR: self._hs_color,
            ATTR_COLOR_TEMP: self._temp
        }

    async def async_turn_on(self, **kwargs) -> None:
        if ATTR_COLOR_TEMP in kwargs or ATTR_BRIGHTNESS in kwargs:
            if ATTR_BRIGHTNESS in kwargs:
                self._brightness = kwargs[ATTR_BRIGHTNESS]

            if ATTR_COLOR_TEMP in kwargs:
                self._temp = kwargs[ATTR_COLOR_TEMP]

            ch = str(25 + round(self._brightness / 255 * (255 - 25)))
            # type send no matter
            payload = {
                'zyx_mode': 1,
                'channel2': '0',
                'channel3': '0',
                'channel4': '0'
            }
            if self._temp == 1:
                payload.update({'channel0': ch, 'channel1': '0'})
            elif self._temp == 2:
                payload.update({'channel0': ch, 'channel1': ch})
            elif self._temp == 3:
                payload.update({'channel0': '0', 'channel1': ch})

        elif ATTR_HS_COLOR in kwargs:
            rgb = color.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            # type send no matter
            payload = {
                'zyx_mode': 2,
                'channel0': '0',
                'channel1': '0',
                'channel2': str(rgb[0]),
                'channel3': str(rgb[1]),
                'channel4': str(rgb[2]),
            }

        else:
            payload = {'state': 'on'}

        await self.registry.send(self.deviceid, payload)

    async def async_turn_off(self, **kwargs) -> None:
        await self.registry.send(self.deviceid, {'state': 'off'})


class EWeLinkLightGroup(SonoffD1):
    """Differs from the usual switch by brightness adjustment. Is logical
    use only for two or more channels. Able to remember brightness on moment
    off.

    The sequence of channels is important. The first channels will be turned on
    at low brightness.
    """

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        if 'switches' in state:
            # number of active channels
            cnt = sum(self._is_on_list(state))
            if cnt:
                # if at least something is on - remember the new brightness
                self._brightness = round(cnt / len(self.channels) * 255)
                self._is_on = True
            else:
                self._is_on = False

        if 'sledOnline' in state:
            self._sled_online = state['sledOnline']

        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        # how much light should burn at such brightness
        cnt = round(self._brightness / 255 * len(self.channels))

        # if tried to turn it on at zero brightness - turn on all the light
        if cnt == 0 and ATTR_BRIGHTNESS not in kwargs:
            await self._turn_on()
            return

        # the first part of the lights - turn on, the second - turn off
        channels = {
            channel: i < cnt
            for i, channel in enumerate(self.channels)
        }
        await self._turn_bulk(channels)


DIFFUSER_EFFECTS = ["Color Light", "RGB Color", "Night Light"]


class SonoffDiffuserLight(EWeLinkToggle):
    _brightness = 0
    _hs_color = None
    _mode = 0

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        if 'lightbright' in state:
            # brightness from 0 to 100
            self._brightness = max(round(state['lightbright'] * 2.55), 1)

        if 'lightmode' in state:
            self._mode = state['lightmode']

        if 'lightRcolor' in state:
            self._hs_color = color.color_RGB_to_hs(
                state['lightRcolor'], state['lightGcolor'],
                state['lightBcolor'])

        if 'lightswitch' in state:
            self._is_on = state['lightswitch'] == 1

        self.schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return self._hs_color

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return DIFFUSER_EFFECTS

    @property
    def effect(self):
        """Return the current effect."""
        return DIFFUSER_EFFECTS[self._mode - 1]

    @property
    def supported_features(self):
        if self._mode == 1:
            return SUPPORT_EFFECT
        elif self._mode == 2:
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_EFFECT
        elif self._mode == 3:
            return SUPPORT_BRIGHTNESS | SUPPORT_EFFECT

    @property
    def state_attributes(self):
        return {
            **self._attrs,
            ATTR_BRIGHTNESS: self.brightness,
            ATTR_HS_COLOR: self._hs_color,
            ATTR_EFFECT: self.effect
        }

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        return {ATTR_EFFECT_LIST: self.effect_list}

    async def async_turn_off(self, **kwargs) -> None:
        await self.registry.send(self.deviceid, {'lightswitch': 0})

    async def async_turn_on(self, **kwargs) -> None:
        payload = {}

        if ATTR_EFFECT in kwargs:
            mode = DIFFUSER_EFFECTS.index(kwargs[ATTR_EFFECT]) + 1
            payload['lightmode'] = mode

            if mode == 2 and ATTR_HS_COLOR not in kwargs:
                kwargs[ATTR_HS_COLOR] = self._hs_color

        if ATTR_BRIGHTNESS in kwargs:
            br = max(round(kwargs[ATTR_BRIGHTNESS] / 2.55), 1)
            payload['lightbright'] = br

        if ATTR_HS_COLOR in kwargs:
            rgb = color.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            payload.update({'lightmode': 2, 'lightRcolor': rgb[0],
                            'lightGcolor': rgb[1], 'lightBcolor': rgb[2]})

        if not kwargs:
            payload['lightswitch'] = 1

        await self.registry.send(self.deviceid, payload)
