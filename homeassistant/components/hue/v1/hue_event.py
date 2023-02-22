"""Representation of a Hue remote firing events for button presses."""
import logging

from aiohue.v1.sensors import (
    EVENT_BUTTON,
    TYPE_ZGP_SWITCH,
    TYPE_ZLL_ROTARY,
    TYPE_ZLL_SWITCH,
)

from homeassistant.const import CONF_DEVICE_ID, CONF_EVENT, CONF_ID, CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util, slugify

from ..const import ATTR_HUE_EVENT
from .sensor_device import GenericHueDevice

LOGGER = logging.getLogger(__name__)

CONF_LAST_UPDATED = "last_updated"

EVENT_NAME_FORMAT = "{}"


class HueEvent(GenericHueDevice):
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, sensor, name, bridge, primary_sensor=None):
        """Register callback that will be used for signals."""
        super().__init__(sensor, name, bridge, primary_sensor)
        self.device_registry_id = None

        self.event_id = slugify(self.sensor.name)
        # Use the aiohue sensor 'state' dict to detect new remote presses
        self._last_state = dict(self.sensor.state)

        # Register callback in coordinator and add job to remove it on bridge reset.
        self.bridge.reset_jobs.append(
            self.bridge.sensor_manager.coordinator.async_add_listener(
                self.async_update_callback
            )
        )

    @callback
    def async_update_callback(self):
        """Fire the event if reason is that state is updated."""
        if (
            self.sensor.state == self._last_state
            # Filter out non-button events if last event type is available
            or (
                self.sensor.last_event is not None
                and self.sensor.last_event["type"] != EVENT_BUTTON
            )
        ):
            return

        # Filter out old states. Can happen when events fire while refreshing
        now_updated = dt_util.parse_datetime(self.sensor.state["lastupdated"])
        last_updated = dt_util.parse_datetime(self._last_state["lastupdated"])

        if (
            now_updated is not None
            and last_updated is not None
            and now_updated <= last_updated
        ):
            return

        # Extract the press code as state
        if hasattr(self.sensor, "rotaryevent"):
            state = self.sensor.rotaryevent
        else:
            state = self.sensor.buttonevent

        self._last_state = dict(self.sensor.state)

        # Fire event
        data = {
            CONF_ID: self.event_id,
            CONF_DEVICE_ID: self.device_registry_id,
            CONF_UNIQUE_ID: self.unique_id,
            CONF_EVENT: state,
            CONF_LAST_UPDATED: self.sensor.lastupdated,
        }
        self.bridge.hass.bus.async_fire(ATTR_HUE_EVENT, data)

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = dr.async_get(self.bridge.hass)

        entry = device_registry.async_get_or_create(
            config_entry_id=self.bridge.config_entry.entry_id, **self.device_info
        )
        self.device_registry_id = entry.id
        LOGGER.debug(
            "Event registry with entry_id: %s and device_id: %s",
            self.device_registry_id,
            self.device_id,
        )


EVENT_CONFIG_MAP = {
    TYPE_ZGP_SWITCH: {"name_format": EVENT_NAME_FORMAT, "class": HueEvent},
    TYPE_ZLL_SWITCH: {"name_format": EVENT_NAME_FORMAT, "class": HueEvent},
    TYPE_ZLL_ROTARY: {"name_format": EVENT_NAME_FORMAT, "class": HueEvent},
}
