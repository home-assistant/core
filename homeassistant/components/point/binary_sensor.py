"""Support for Minut Point binary sensors."""

from __future__ import annotations

import logging

from pypoint import EVENTS

from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinutPointEntity
from .const import DOMAIN as POINT_DOMAIN, POINT_DISCOVERY_NEW, SIGNAL_WEBHOOK

_LOGGER = logging.getLogger(__name__)


DEVICES = {
    "alarm": {"icon": "mdi:alarm-bell"},
    "battery": {"device_class": BinarySensorDeviceClass.BATTERY},
    "button_press": {"icon": "mdi:gesture-tap-button"},
    "cold": {"device_class": BinarySensorDeviceClass.COLD},
    "connectivity": {"device_class": BinarySensorDeviceClass.CONNECTIVITY},
    "dry": {"icon": "mdi:water"},
    "glass": {"icon": "mdi:window-closed-variant"},
    "heat": {"device_class": BinarySensorDeviceClass.HEAT},
    "moisture": {"device_class": BinarySensorDeviceClass.MOISTURE},
    "motion": {"device_class": BinarySensorDeviceClass.MOTION},
    "noise": {"icon": "mdi:volume-high"},
    "sound": {"device_class": BinarySensorDeviceClass.SOUND},
    "tamper_old": {"icon": "mdi:shield-alert"},
    "tamper": {"icon": "mdi:shield-alert"},
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Point's binary sensors based on a config entry."""

    async def async_discover_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[POINT_DOMAIN][config_entry.entry_id]
        async_add_entities(
            (
                MinutPointBinarySensor(client, device_id, device_name)
                for device_name in DEVICES
                if device_name in EVENTS
            ),
            True,
        )

    async_dispatcher_connect(
        hass, POINT_DISCOVERY_NEW.format(DOMAIN, POINT_DOMAIN), async_discover_sensor
    )


class MinutPointBinarySensor(MinutPointEntity, BinarySensorEntity):
    """The platform class required by Home Assistant."""

    def __init__(self, point_client, device_id, device_name):
        """Initialize the binary sensor."""
        super().__init__(
            point_client,
            device_id,
            DEVICES[device_name].get("device_class", device_name),
        )
        self._device_name = device_name
        self._async_unsub_hook_dispatcher_connect = None
        self._events = EVENTS[device_name]
        self._attr_unique_id = f"point.{device_id}-{device_name}"
        self._attr_icon = DEVICES[self._device_name].get("icon")

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to HOme Assistant."""
        await super().async_added_to_hass()
        self._async_unsub_hook_dispatcher_connect = async_dispatcher_connect(
            self.hass, SIGNAL_WEBHOOK, self._webhook_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        await super().async_will_remove_from_hass()
        if self._async_unsub_hook_dispatcher_connect:
            self._async_unsub_hook_dispatcher_connect()

    async def _update_callback(self):
        """Update the value of the sensor."""
        if not self.is_updated:
            return
        if self.device_class == BinarySensorDeviceClass.CONNECTIVITY:
            # connectivity is the other way around.
            self._attr_is_on = self._events[0] not in self.device.ongoing_events
        else:
            self._attr_is_on = self._events[0] in self.device.ongoing_events
        self.async_write_ha_state()

    @callback
    def _webhook_event(self, data, webhook):
        """Process new event from the webhook."""
        if self.device.webhook != webhook:
            return
        _type = data.get("event", {}).get("type")
        _device_id = data.get("event", {}).get("device_id")
        if _type not in self._events or _device_id != self.device.device_id:
            return
        _LOGGER.debug("Received webhook: %s", _type)
        if _type == self._events[0]:
            _is_on = True
        elif _type == self._events[1]:
            _is_on = False
        else:
            return

        if self.device_class == BinarySensorDeviceClass.CONNECTIVITY:
            # connectivity is the other way around.
            self._attr_is_on = not _is_on
        else:
            self._attr_is_on = _is_on
        self.async_write_ha_state()
