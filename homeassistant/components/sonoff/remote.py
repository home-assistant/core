"""
Firmware   | LAN type  | uiid | Product Model
-----------|-----------|------|--------------
PSF-BRA-GL | rf        | 28   | RFBridge (Sonoff RF Bridge)
"""
import asyncio
import logging

from homeassistant.components.remote import ATTR_DELAY_SECS, ATTR_COMMAND, \
    SUPPORT_LEARN_COMMAND, DEFAULT_DELAY_SECS

from . import DOMAIN
from .sonoff_main import EWeLinkRegistry
from .switch import EWeLinkToggle

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    if discovery_info is None:
        return

    deviceid = discovery_info['deviceid']
    registry = hass.data[DOMAIN]
    add_entities([EWeLinkRemote(registry, deviceid)])


class EWeLinkRemote(EWeLinkToggle):
    _is_on = True

    def __init__(self, registry: EWeLinkRegistry, deviceid: str):
        super().__init__(registry, deviceid)

        # init button names
        self._buttons = {}
        device = registry.devices[deviceid]
        for remote in device.get('tags', {}).get('zyx_info', []):
            buttons = remote['buttonName']
            if len(buttons) > 1:
                for button in buttons:
                    self._buttons.update(button)
            else:
                k = next(iter(buttons[0]))
                self._buttons.update({k: remote['name']})

    async def async_added_to_hass(self) -> None:
        self._init(force_refresh=False)

    def _update_handler(self, state: dict, attrs: dict):
        """
        Cloud States:
        - {'cmd': 'trigger', 'rfTrig0': '2020-05-10T14:10:17.000Z'}
        - {'cmd': 'transmit', 'rfChl': 3}
        - {'cmd': 'capture', 'rfChl': 1},
        """
        if not self._is_on:
            return

        self._attrs.update(attrs)

        if 'sledOnline' in state:
            self._sled_online = state['sledOnline']

        for k, v in state.items():
            if k.startswith('rfTrig'):
                if v == self._attrs.get('ts'):
                    # skip same cmd from local and cloud
                    return

                channel = k[6:]
                data = {'command': int(channel), 'ts': v,
                        'name': self._buttons.get(channel)}
                self._attrs.update(data)

                data['entity_id'] = self.entity_id
                _LOGGER.debug(f"Fire event sonoff.remote: {data}")
                self.hass.bus.fire('sonoff.remote', data)

                self.schedule_update_ha_state()

    @property
    def supported_features(self):
        return SUPPORT_LEARN_COMMAND

    async def async_turn_on(self, **kwargs):
        self._is_on = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        self._is_on = False
        self.schedule_update_ha_state()

    async def async_send_command(self, command, **kwargs):
        if not self._is_on:
            return

        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        for i, channel in enumerate(command):
            if i:
                await asyncio.sleep(delay)

            if not channel.isdigit():
                channel = next((k for k, v in self._buttons.items()
                                if v == channel), None)

            if channel is None:
                _LOGGER.error(f"Not found RF button for {command}")
                return

            # cmd param for local and for cloud mode
            await self.registry.send(self.deviceid, {
                'cmd': 'transmit', 'rfChl': int(channel)})

    async def async_learn_command(self, **kwargs):
        if not self._is_on:
            return

        command = kwargs[ATTR_COMMAND]
        # cmd param for local and for cloud mode
        await self.registry.send(self.deviceid, {
            'cmd': 'capture', 'rfChl': int(command[0])})
