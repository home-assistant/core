import logging
from typing import Optional

from homeassistant.components.cover import ATTR_POSITION, ATTR_CURRENT_POSITION
from homeassistant.const import STATE_OPENING, STATE_CLOSING

from . import DOMAIN
from .sonoff_main import EWeLinkDevice
from .utils import CoverEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    if discovery_info is None:
        return

    deviceid = discovery_info['deviceid']
    registry = hass.data[DOMAIN]
    add_entities([EWeLinkCover(registry, deviceid)])


class EWeLinkCover(CoverEntity, EWeLinkDevice):
    """King Art - King Q4 Cover
    switch=on - open
    switch=off - close
    setclose - position from 0 (open)  to 100 (closed)
    """
    _position = None
    _action = None

    async def async_added_to_hass(self) -> None:
        self._init()

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        # skip any full state update except first one
        if self._position and len(state) > 2:
            return

        if 'setclose' in state:
            newposition = 100 - state['setclose']
            # finished the movement (on - opening, off - closing)
            if 'switch' in state:
                self._action = None
                # reversed position: HA closed at 0, eWeLink closed at 100
                self._position = newposition
            elif newposition > self._position:
                self._action = STATE_OPENING
            elif newposition < self._position:
                self._action = STATE_CLOSING

        # full open or full close command
        elif 'switch' in state:
            if state['switch'] == 'on':
                self._action = STATE_OPENING
            elif state['switch'] == 'off':
                self._action = STATE_CLOSING
            else:
                self._action = None

        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self) -> Optional[str]:
        return self.deviceid

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def state_attributes(self):
        return {
            **self._attrs,
            ATTR_CURRENT_POSITION: self.current_cover_position
        }

    @property
    def available(self) -> bool:
        device: dict = self.registry.devices[self.deviceid]
        return device['available']

    @property
    def current_cover_position(self):
        return self._position

    @property
    def is_opening(self):
        return self._action == STATE_OPENING

    @property
    def is_closing(self):
        return self._action == STATE_CLOSING

    @property
    def is_closed(self):
        return self._position == 0

    async def async_open_cover(self, **kwargs):
        self._action = STATE_OPENING
        await self.registry.send(self.deviceid, {'switch': 'on'})

    async def async_close_cover(self, **kwargs):
        self._action = STATE_CLOSING
        await self.registry.send(self.deviceid, {'switch': 'off'})

    async def async_set_cover_position(self, **kwargs):
        newposition = kwargs.get(ATTR_POSITION)
        if newposition > self._position:
            self._action = STATE_OPENING
        elif newposition < self._position:
            self._action = STATE_CLOSING
        self._position = newposition

        await self.registry.send(self.deviceid, {
            'setclose': 100 - newposition})

    async def async_stop_cover(self, **kwargs):
        self._action = None
        await self.registry.send(self.deviceid, {'switch': 'pause'})
