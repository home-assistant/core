"""Device entity for Zigbee Home Automation."""

import logging
import time

from homeassistant.core import callback
from homeassistant.util import slugify
from .entity import ZhaEntity
from .const import POWER_CONFIGURATION_CHANNEL, SIGNAL_STATE_ATTR

_LOGGER = logging.getLogger(__name__)

BATTERY_SIZES = {
    0: 'No battery',
    1: 'Built in',
    2: 'Other',
    3: 'AA',
    4: 'AAA',
    5: 'C',
    6: 'D',
    7: 'CR2',
    8: 'CR123A',
    9: 'CR2450',
    10: 'CR2032',
    11: 'CR1632',
    255: 'Unknown'
}

STATE_ONLINE = 'online'
STATE_OFFLINE = 'offline'


class ZhaDeviceEntity(ZhaEntity):
    """A base class for ZHA devices."""

    def __init__(self, zha_device, channels, keepalive_interval=7200,
                 **kwargs):
        """Init ZHA endpoint entity."""
        ieee = zha_device.ieee
        ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
        unique_id = None
        if zha_device.manufacturer is not None and \
                zha_device.model is not None:
            unique_id = "{}_{}_{}".format(
                slugify(zha_device.manufacturer),
                slugify(zha_device.model),
                ieeetail,
            )
        else:
            unique_id = str(ieeetail)

        kwargs['component'] = 'zha'
        super().__init__(unique_id, zha_device, channels, skip_entity_id=True,
                         **kwargs)

        self._keepalive_interval = keepalive_interval
        self._device_state_attributes.update({
            'nwk': '0x{0:04x}'.format(zha_device.nwk),
            'ieee': str(zha_device.ieee),
            'lqi': zha_device.lqi,
            'rssi': zha_device.rssi,
        })
        self._should_poll = True
        self._battery_channel = self.cluster_channels.get(
            POWER_CONFIGURATION_CHANNEL)

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._state

    @property
    def available(self):
        """Return True if device is available."""
        return self._zha_device.available

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        update_time = None
        device = self._zha_device
        if device.last_seen is not None and not self.available:
            time_struct = time.localtime(device.last_seen)
            update_time = time.strftime("%Y-%m-%dT%H:%M:%S", time_struct)
            self._device_state_attributes['last_seen'] = update_time
        if ('last_seen' in self._device_state_attributes and
                self.available):
            del self._device_state_attributes['last_seen']
        self._device_state_attributes['lqi'] = device.lqi
        self._device_state_attributes['rssi'] = device.rssi
        return self._device_state_attributes

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_check_recently_seen()
        if self._battery_channel:
            await self.async_accept_signal(
                self._battery_channel, SIGNAL_STATE_ATTR,
                self.async_update_state_attribute)
            # only do this on add to HA because it is static
            await self._async_init_battery_values()

    async def async_update(self):
        """Handle polling."""
        if self._zha_device.last_seen is None:
            self._zha_device.update_available(False)
        else:
            difference = time.time() - self._zha_device.last_seen
            if difference > self._keepalive_interval:
                self._zha_device.update_available(False)
            else:
                self._zha_device.update_available(True)
                if self._battery_channel:
                    await self.async_get_latest_battery_reading()

    @callback
    def async_set_available(self, available):
        """Set entity availability."""
        if available:
            self._state = STATE_ONLINE
        else:
            self._state = STATE_OFFLINE
        super().async_set_available(available)

    async def _async_init_battery_values(self):
        """Get initial battery level and battery info from channel cache."""
        battery_size = await self._battery_channel.get_attribute_value(
            'battery_size')
        if battery_size is not None:
            self._device_state_attributes['battery_size'] = BATTERY_SIZES.get(
                battery_size, 'Unknown')

        battery_quantity = await self._battery_channel.get_attribute_value(
            'battery_quantity')
        if battery_quantity is not None:
            self._device_state_attributes['battery_quantity'] = \
                battery_quantity
        await self.async_get_latest_battery_reading()

    async def async_get_latest_battery_reading(self):
        """Get the latest battery reading from channels cache."""
        battery = await self._battery_channel.get_attribute_value(
            'battery_percentage_remaining')
        # per zcl specs battery percent is reported at 200% ¯\_(ツ)_/¯
        if battery is not None and battery != -1:
            battery = battery / 2
            battery = int(round(battery))
            self._device_state_attributes['battery_level'] = battery
