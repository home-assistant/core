"""
Firmware   | LAN type  | uiid | Product Model
-----------|-----------|------|--------------
PSF-B04-GL | strip     | 34   | iFan02 (Sonoff iFan02)
PSF-BFB-GL | fan_light | 34   | iFan (Sonoff iFan03)

https://github.com/AlexxIT/SonoffLAN/issues/30
"""
from typing import Optional, List

from homeassistant.components.fan import FanEntity, SUPPORT_SET_SPEED, \
    SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH, SPEED_OFF, ATTR_SPEED

# noinspection PyUnresolvedReferences
from . import DOMAIN, SCAN_INTERVAL
from .sonoff_main import EWeLinkDevice
from .switch import EWeLinkToggle

IFAN02_CHANNELS = [2, 3, 4]
IFAN02_STATES = {
    SPEED_OFF: {2: False},
    SPEED_LOW: {2: True, 3: False, 4: False},
    SPEED_MEDIUM: {2: True, 3: True, 4: False},
    SPEED_HIGH: {2: True, 3: False, 4: True}
}


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    if discovery_info is None:
        return

    deviceid = discovery_info['deviceid']
    channels = discovery_info['channels']
    registry = hass.data[DOMAIN]
    device = registry.devices[deviceid]
    uiid = device.get('uiid')
    # iFan02 and iFan03 have the same uiid!
    if uiid == 34 or uiid == 'fan_light':
        # only channel 2 is used for switching
        add_entities([SonoffFan02(registry, deviceid, [2])])
    elif uiid == 25:
        add_entities([SonoffDiffuserFan(registry, deviceid)])
    else:
        add_entities([EWeLinkToggle(registry, deviceid, channels)])


class SonoffFanBase(FanEntity, EWeLinkDevice):
    _speed = None

    async def async_added_to_hass(self) -> None:
        self._init()

    @property
    def should_poll(self) -> bool:
        # The device itself sends an update of its status
        return False

    @property
    def unique_id(self) -> Optional[str]:
        return self.deviceid

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def available(self) -> bool:
        device: dict = self.registry.devices[self.deviceid]
        return device['available']

    @property
    def supported_features(self):
        return SUPPORT_SET_SPEED

    @property
    def speed(self) -> Optional[str]:
        return self._speed

    @property
    def speed_list(self) -> list:
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def state_attributes(self) -> dict:
        return {
            **self._attrs,
            ATTR_SPEED: self.speed
        }


class SonoffFan02(SonoffFanBase):
    def _is_on_list(self, state: dict) -> List[bool]:
        # https://github.com/AlexxIT/SonoffLAN/issues/146
        switches = sorted(state['switches'], key=lambda i: i['outlet'])
        return [
            switches[channel - 1]['switch'] == 'on'
            for channel in IFAN02_CHANNELS
        ]

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        if 'switches' in state:
            mask = self._is_on_list(state)
            if mask[0]:
                if not mask[1] and not mask[2]:
                    self._speed = SPEED_LOW
                elif mask[1] and not mask[2]:
                    self._speed = SPEED_MEDIUM
                elif not mask[1] and mask[2]:
                    self._speed = SPEED_HIGH
                else:
                    raise Exception("Wrong iFan02 state")
            else:
                self._speed = SPEED_OFF

        self.schedule_update_ha_state()

    async def async_set_speed(self, speed: str) -> None:
        channels = IFAN02_STATES.get(speed)
        await self._turn_bulk(channels)

    async def async_turn_on(self, speed: Optional[str] = None, **kwargs):
        if speed:
            await self.async_set_speed(speed)
        else:
            await self._turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        await self._turn_off()


class SonoffDiffuserFan(SonoffFanBase):
    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        if 'switch' in state:
            self._is_on = state['switch'] == 'on'

        if 'state' in state:
            if state['state'] == 1:
                self._speed = SPEED_LOW
            elif state['state'] == 2:
                self._speed = SPEED_HIGH

        self.schedule_update_ha_state()

    @property
    def speed(self) -> Optional[str]:
        return self._speed if self._is_on else SPEED_OFF

    @property
    def speed_list(self) -> list:
        return [SPEED_OFF, SPEED_LOW, SPEED_HIGH]

    async def async_set_speed(self, speed: str) -> None:
        if speed == SPEED_HIGH:
            await self.registry.send(self.deviceid,
                                     {'switch': 'on', 'state': 2})
        elif speed == SPEED_LOW:
            await self.registry.send(self.deviceid,
                                     {'switch': 'on', 'state': 1})
        elif speed == SPEED_OFF:
            await self._turn_off()

    async def async_turn_on(self, speed: Optional[str] = None, **kwargs):
        if speed:
            await self.async_set_speed(speed)
        else:
            await self._turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        await self._turn_off()
