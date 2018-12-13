"""
Device entity for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import time

from homeassistant.helpers import entity
from homeassistant.util import slugify


class ZhaDeviceEntity(entity.Entity):
    """A base class for ZHA devices."""

    def __init__(self, device, manufacturer, model, application_listener,
                 keepalive_interval=7200, **kwargs):
        """Init ZHA endpoint entity."""
        self._device_state_attributes = {
            'nwk': '0x{0:04x}'.format(device.nwk),
            'ieee': str(device.ieee),
            'lqi': device.lqi,
            'rssi': device.rssi,
        }

        ieee = device.ieee
        ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
        if manufacturer is not None and model is not None:
            self._unique_id = "{}_{}_{}".format(
                slugify(manufacturer),
                slugify(model),
                ieeetail,
            )
            self._device_state_attributes['friendly_name'] = "{} {}".format(
                manufacturer,
                model,
            )
        else:
            self._unique_id = str(ieeetail)

        self._device = device
        self._state = 'offline'
        self._keepalive_interval = keepalive_interval

        application_listener.register_entity(ieee, self)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        update_time = None
        if self._device.last_seen is not None and self._state == 'offline':
            time_struct = time.localtime(self._device.last_seen)
            update_time = time.strftime("%Y-%m-%dT%H:%M:%S", time_struct)
            self._device_state_attributes['last_seen'] = update_time
        if ('last_seen' in self._device_state_attributes and
                self._state != 'offline'):
            del self._device_state_attributes['last_seen']
        self._device_state_attributes['lqi'] = self._device.lqi
        self._device_state_attributes['rssi'] = self._device.rssi
        return self._device_state_attributes

    async def async_update(self):
        """Handle polling."""
        if self._device.last_seen is None:
            self._state = 'offline'
        else:
            difference = time.time() - self._device.last_seen
            if difference > self._keepalive_interval:
                self._state = 'offline'
            else:
                self._state = 'online'
