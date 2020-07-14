import json
from typing import Optional

from homeassistant.components.binary_sensor import DEVICE_CLASS_DOOR
from homeassistant.const import CONF_DEVICE_CLASS, CONF_TIMEOUT, \
    CONF_PAYLOAD_OFF
from homeassistant.core import Event
from homeassistant.helpers.event import async_call_later

from . import DOMAIN
from .sonoff_main import EWeLinkDevice
from .utils import BinarySensorEntity


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    if discovery_info is None:
        return

    # sonoff rf bridge sensor
    if 'deviceid' not in discovery_info:
        add_entities([RFBridgeSensor(discovery_info)])
        return

    deviceid = discovery_info['deviceid']
    registry = hass.data[DOMAIN]
    device = registry.devices[deviceid]
    if device.get('uiid') == 102:
        add_entities([DoorWindowSensor(registry, deviceid)])
    else:
        add_entities([EWeLinkBinarySensor(registry, deviceid)])


class EWeLinkBinarySensor(BinarySensorEntity, EWeLinkDevice):
    async def async_added_to_hass(self) -> None:
        self._init()

    def _update_handler(self, state: dict, attrs: dict):
        state = {k: json.dumps(v) for k, v in state.items()}
        self._attrs.update(state)
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
        return self._attrs

    @property
    def supported_features(self):
        return 0

    @property
    def is_on(self):
        return self._is_on


class DoorWindowSensor(EWeLinkBinarySensor):
    _device_class = None

    async def async_added_to_hass(self) -> None:
        device: dict = self.registry.devices[self.deviceid]
        self._device_class = device.get('device_class', DEVICE_CLASS_DOOR)

        self._init()

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        if 'switch' in state:
            self._is_on = state['switch'] == 'on'

        self.schedule_update_ha_state()

    @property
    def available(self) -> bool:
        device: dict = self.registry.devices[self.deviceid]
        return device['available']

    @property
    def device_class(self):
        return self._device_class


class RFBridgeSensor(BinarySensorEntity):
    _is_on = False
    _unsub_turn_off = None

    def __init__(self, config: dict):
        self.payload_off = config.get(CONF_PAYLOAD_OFF)
        self.timeout = config.get(CONF_TIMEOUT)
        self.trigger = config.get('trigger')

        self._device_class = config.get(CONF_DEVICE_CLASS)
        self._name = config.get('name') or self.trigger

    async def async_added_to_hass(self) -> None:
        self.hass.bus.async_listen('sonoff.remote', self._update_handler)

    async def _update_handler(self, event: Event):
        if self.payload_off and event.data['name'] == self.payload_off:
            if self._unsub_turn_off:
                self._unsub_turn_off()

            if self._is_on:
                self._is_on = False
                self.schedule_update_ha_state()

        elif event.data['name'] == self.trigger:
            if self._unsub_turn_off:
                self._unsub_turn_off()

            if self.timeout:
                self._unsub_turn_off = async_call_later(
                    self.hass, self.timeout, self._turn_off)

            if not self._is_on:
                self._is_on = True
                self.schedule_update_ha_state()

    async def _turn_off(self, now):
        self._unsub_turn_off = None
        self._is_on = False
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def is_on(self):
        return self._is_on

    @property
    def device_class(self):
        return self._device_class
