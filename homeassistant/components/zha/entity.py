"""
Entity for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import logging
import time

from homeassistant.core import callback
from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from .core.const import (
    DOMAIN, ATTR_MANUFACTURER, DATA_ZHA, DATA_ZHA_BRIDGE_ID, MODEL, NAME,
    SIGNAL_REMOVE
)
from .core.channels import MAINS_POWERED

_LOGGER = logging.getLogger(__name__)

ENTITY_SUFFIX = 'entity_suffix'
RESTART_GRACE_PERIOD = 7200  # 2 hours


class ZhaEntity(RestoreEntity, entity.Entity):
    """A base class for ZHA entities."""

    _domain = None  # Must be overridden by subclasses

    def __init__(self, unique_id, zha_device, channels,
                 skip_entity_id=False, **kwargs):
        """Init ZHA entity."""
        self._force_update = False
        self._should_poll = False
        self._unique_id = unique_id
        self._name = None
        if zha_device.manufacturer and zha_device.model is not None:
            self._name = "{} {}".format(
                zha_device.manufacturer,
                zha_device.model
            )
        if not skip_entity_id:
            ieee = zha_device.ieee
            ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
            if zha_device.manufacturer and zha_device.model is not None:
                self.entity_id = "{}.{}_{}_{}_{}{}".format(
                    self._domain,
                    slugify(zha_device.manufacturer),
                    slugify(zha_device.model),
                    ieeetail,
                    channels[0].cluster.endpoint.endpoint_id,
                    kwargs.get(ENTITY_SUFFIX, ''),
                )
            else:
                self.entity_id = "{}.zha_{}_{}{}".format(
                    self._domain,
                    ieeetail,
                    channels[0].cluster.endpoint.endpoint_id,
                    kwargs.get(ENTITY_SUFFIX, ''),
                )
        self._state = None
        self._device_state_attributes = {}
        self._zha_device = zha_device
        self.cluster_channels = {}
        self._available = False
        self._component = kwargs['component']
        self._unsubs = []
        for channel in channels:
            self.cluster_channels[channel.name] = channel

    @property
    def name(self):
        """Return Entity's default name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def zha_device(self):
        """Return the zha device this entity is attached to."""
        return self._zha_device

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._device_state_attributes

    @property
    def force_update(self) -> bool:
        """Force update this entity."""
        return self._force_update

    @property
    def should_poll(self) -> bool:
        """Poll state from device."""
        return self._should_poll

    @property
    def device_info(self):
        """Return a device description for device registry."""
        zha_device_info = self._zha_device.device_info
        ieee = zha_device_info['ieee']
        return {
            'connections': {(CONNECTION_ZIGBEE, ieee)},
            'identifiers': {(DOMAIN, ieee)},
            ATTR_MANUFACTURER: zha_device_info[ATTR_MANUFACTURER],
            MODEL: zha_device_info[MODEL],
            NAME: zha_device_info[NAME],
            'via_hub': (DOMAIN, self.hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID]),
        }

    @property
    def available(self):
        """Return entity availability."""
        return self._available

    def async_set_available(self, available):
        """Set entity availability."""
        self._available = available
        self.async_schedule_update_ha_state()

    def async_update_state_attribute(self, key, value):
        """Update a single device state attribute."""
        self._device_state_attributes.update({
            key: value
        })
        self.async_schedule_update_ha_state()

    def async_set_state(self, state):
        """Set the entity state."""
        pass

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_check_recently_seen()
        await self.async_accept_signal(
            None, "{}_{}".format(self.zha_device.available_signal, 'entity'),
            self.async_set_available,
            signal_override=True)
        await self.async_accept_signal(
            None, "{}_{}".format(SIGNAL_REMOVE, str(self.zha_device.ieee)),
            self.async_remove,
            signal_override=True
        )
        self._zha_device.gateway.register_entity_reference(
            self._zha_device.ieee, self.entity_id, self._zha_device,
            self.cluster_channels, self.device_info)

    async def async_check_recently_seen(self):
        """Check if the device was seen within the last 2 hours."""
        last_state = await self.async_get_last_state()
        if last_state and self._zha_device.last_seen and (
                time.time() - self._zha_device.last_seen <
                RESTART_GRACE_PERIOD):
            self.async_set_available(True)
            if self.zha_device.power_source != MAINS_POWERED:
                # mains powered devices will get real time state
                self.async_restore_last_state(last_state)
            self._zha_device.set_available(True)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        for unsub in self._unsubs:
            unsub()

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        pass

    async def async_update(self):
        """Retrieve latest state."""
        for channel in self.cluster_channels.values():
            if hasattr(channel, 'async_update'):
                await channel.async_update()

    async def async_accept_signal(self, channel, signal, func,
                                  signal_override=False):
        """Accept a signal from a channel."""
        unsub = None
        if signal_override:
            unsub = async_dispatcher_connect(
                self.hass,
                signal,
                func
            )
        else:
            unsub = async_dispatcher_connect(
                self.hass,
                "{}_{}".format(channel.unique_id, signal),
                func
            )
        self._unsubs.append(unsub)
