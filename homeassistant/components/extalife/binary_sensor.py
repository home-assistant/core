"""Support for Exta Life binary sensor devices e.g. leakage sensor, door/window open sensor"""
import logging
from pprint import pformat

from homeassistant.components.binary_sensor import (
    DOMAIN as DOMAIN_BINARY_SENSOR,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import ExtaLifeChannel
from .helpers.const import DOMAIN
from .helpers.core import Core
from .pyextalife import (
    DEVICE_ARR_SENS_MOTION,
    DEVICE_ARR_SENS_OPENCLOSE,
    DEVICE_ARR_SENS_WATER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """"setup via configuration.yaml not supported anymore"""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up Exta Life binary sensors based on existing config."""

    core = Core.get(config_entry.entry_id)
    channels = core.get_channels(DOMAIN_BINARY_SENSOR)

    _LOGGER.debug("Discovery: %s", pformat(channels))
    async_add_entities(
        [ExtaLifeBinarySensor(device, config_entry) for device in channels]
    )

    core.pop_channels(DOMAIN_BINARY_SENSOR)


class ExtaLifeBinarySensor(ExtaLifeChannel, BinarySensorEntity):
    """Representation of an ExtaLife binary sensors"""

    def __init__(self, channel_data, config_entry):
        super().__init__(channel_data, config_entry)
        self._dev_type = None
        self._dev_class = None

        dev_type = self.channel_data.get("type")
        if dev_type in DEVICE_ARR_SENS_WATER:
            self._dev_class = "moisture"

        if dev_type in DEVICE_ARR_SENS_MOTION:
            self._dev_class = "motion"

        if dev_type in DEVICE_ARR_SENS_OPENCLOSE:
            self._dev_class = "opening"

        self._dev_type = dev_type
        self._attributes = dict()

    @property
    def is_on(self):
        """Return state of the sensor"""
        # Exta Life detection sensors keep their bollean status in field value_3
        state = self.channel_data.get("value_3")

        if self._dev_type in DEVICE_ARR_SENS_WATER:
            value = state

        elif self._dev_type in DEVICE_ARR_SENS_MOTION:
            value = state

        elif self._dev_type in DEVICE_ARR_SENS_OPENCLOSE:
            value = not state
        else:
            value = state

        _LOGGER.debug(
            "state update 'is_on' for entity: %s, id: %s. Status to be updated: %s",
            self.entity_id,
            self.channel_id,
            value,
        )
        return value

    @property
    def device_class(self):
        return self._dev_class

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        data = self.channel_data.get("data")
        # general sensor attributes
        if data.get("sync_time") is not None:
            self._attributes.update({"sync_time": data.get("sync_time")})
        if data.get("last_sync") is not None:
            self._attributes.update({"last_sync": data.get("last_sync")})
        if data.get("battery_status") is not None:
            self._attributes.update({"battery_status": data.get("battery_status")})

        # motion sensor attributes
        if self._dev_class == "motion":
            self._attributes.update({"tamper": data.get("tamper")})
            self._attributes.update({"tamper_sync_time": data.get("tamper_sync_time")})

        return self._attributes

    def on_state_notification(self, data):
        """ React on state notification from controller """
        state = data.get("state")
        ch_data = self.channel_data.copy()

        ch_data["value_3"] = state

        _LOGGER.debug(
            "on_state_notification for entity: %s, id: %s. Status to be updated: %s",
            self.entity_id,
            self.channel_id,
            state,
        )

        # update only if notification data contains new status; prevent HS event bus overloading
        if ch_data != self.channel_data:
            self.channel_data.update(ch_data)

            # synchronize DataManager data with processed update & entity data
            self.sync_data_update_ha()
