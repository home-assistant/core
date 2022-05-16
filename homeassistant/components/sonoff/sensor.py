import time
from typing import Optional

from homeassistant.const import DEVICE_CLASS_TEMPERATURE, \
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_POWER, \
    DEVICE_CLASS_SIGNAL_STRENGTH, ATTR_BATTERY_LEVEL
from homeassistant.helpers.entity import Entity

from . import DOMAIN, EWeLinkRegistry
from .sonoff_main import EWeLinkDevice

SENSORS = {
    'temperature': [DEVICE_CLASS_TEMPERATURE, '°C', None],
    # UNIT_PERCENTAGE is not on old versions
    'humidity': [DEVICE_CLASS_HUMIDITY, '%', None],
    'dusty': [None, None, 'mdi:cloud'],
    'light': [DEVICE_CLASS_ILLUMINANCE, None, None],
    'noise': [None, None, 'mdi:bell-ring'],
    'power': [DEVICE_CLASS_POWER, 'W', None],
    'current': [DEVICE_CLASS_POWER, 'A', None],
    'voltage': [DEVICE_CLASS_POWER, 'V', None],
    'rssi': [DEVICE_CLASS_SIGNAL_STRENGTH, 'dBm', None]
}

SONOFF_SC = {'temperature', 'humidity', 'dusty', 'light', 'noise'}

GLOBAL_ATTRS = ('local', 'cloud', 'rssi', ATTR_BATTERY_LEVEL)


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    if discovery_info is None:
        return

    deviceid = discovery_info['deviceid']
    registry = hass.data[DOMAIN]

    attr = discovery_info.get('attribute')
    uiid = registry.devices[deviceid].get('uiid')

    # skip duplicate attribute
    if uiid in (18, 1770) and attr in SONOFF_SC:
        return

    elif attr:
        add_entities([EWeLinkSensor(registry, deviceid, attr)])

    elif uiid == 18:
        add_entities([EWeLinkSensor(registry, deviceid, attr)
                      for attr in SONOFF_SC])

    elif uiid == 1000:
        add_entities([ZigBeeButtonSensor(registry, deviceid)])

    elif uiid == 1770:
        add_entities([EWeLinkSensor(registry, deviceid, 'temperature'),
                      EWeLinkSensor(registry, deviceid, 'humidity')])


class EWeLinkSensor(EWeLinkDevice, Entity):
    _state = None

    def __init__(self, registry: EWeLinkRegistry, deviceid: str, attr: str):
        super().__init__(registry, deviceid)
        self._attr = attr

    async def async_added_to_hass(self) -> None:
        self._init()

        if self._name:
            self._name += f" {self._attr.capitalize()}"

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update({k: attrs[k] for k in GLOBAL_ATTRS if k in attrs})

        if self._attr not in state:
            return

        self._state = state[self._attr]

        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self.deviceid}_{self._attr}"

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def state(self) -> str:
        return self._state

    @property
    def state_attributes(self):
        return self._attrs

    @property
    def available(self) -> bool:
        device: dict = self.registry.devices[self.deviceid]
        return device['available']

    @property
    def device_class(self):
        return SENSORS[self._attr][0] if self._attr in SENSORS else None

    @property
    def unit_of_measurement(self):
        return SENSORS[self._attr][1] if self._attr in SENSORS else None

    @property
    def icon(self):
        return SENSORS[self._attr][2] if self._attr in SENSORS else None


BUTTON_STATES = ['single', 'double', 'hold']


class ZigBeeButtonSensor(EWeLinkDevice, Entity):
    _state = ''

    async def async_added_to_hass(self) -> None:
        # don't call update at startup
        self._init(force_refresh=False)

    def _update_handler(self, state: dict, attrs: dict):
        self._attrs.update(attrs)

        if 'key' in state:
            self._state = BUTTON_STATES[state['key']]
            self.async_write_ha_state()
            time.sleep(.5)
            self._state = ''

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
    def state(self) -> str:
        return self._state

    @property
    def state_attributes(self):
        return self._attrs

    @property
    def available(self) -> bool:
        device: dict = self.registry.devices[self.deviceid]
        return device['available']
