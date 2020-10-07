"""Support for Exta Life roller shutters: SRP, SRM, ROB(future)"""
import logging
from pprint import pformat

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_SHUTTER,
    DOMAIN as DOMAIN_COVER,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import ExtaLifeChannel
from .helpers.const import DOMAIN, OPTIONS_COVER_INVERTED_CONTROL
from .helpers.core import Core
from .pyextalife import (
    DEVICE_ARR_COVER,
    DEVICE_ARR_SENS_GATE_CONTROLLER,
    DEVICE_MAP_TYPE_TO_MODEL,
    MODEL_ROB01,
    MODEL_ROB21,
    ExtaLifeAPI,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """setup via configuration.yaml not supported anymore"""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up Exta Life covers based on existing config."""

    core = Core.get(config_entry.entry_id)
    channels = core.get_channels(DOMAIN_COVER)

    _LOGGER.debug("Discovery: %s", pformat(channels))
    async_add_entities([ExtaLifeCover(device, config_entry) for device in channels])

    core.pop_channels(DOMAIN_COVER)


class ExtaLifeCover(ExtaLifeChannel, CoverEntity):
    """Representation of ExtaLife Cover"""

    # Exta Life extreme cover positions
    POS_CLOSED = 100
    POS_OPEN = 0

    @property
    def device_class(self):
        return DEVICE_CLASS_SHUTTER

    @property
    def supported_features(self):
        dev_type = self.channel_data.get("type")
        if not self.is_exta_free:
            if dev_type in DEVICE_ARR_COVER:
                features = (
                    SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP
                )
                return features
            elif dev_type in DEVICE_ARR_SENS_GATE_CONTROLLER:
                features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
                return features
        else:
            return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def current_cover_position(self):
        """Return current position of cover. 0 is closed, 100 is open."""
        # HA GUI buttons meaning:
        # ARROW UP   - open cover
        # ARROW DOWN - close cover
        # THIS CANNOT BE CHANGED AS IT'S HARDCODED IN HA GUI

        if self.is_exta_free:
            return

        val = self.channel_data.get("value")
        pos = val if self.is_inverted_control else 100 - val

        _LOGGER.debug(
            "current_cover_position for cover: %s. Model: %s, returned to HA: %s",
            self.entity_id,
            val,
            pos,
        )
        return pos

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        data = self.channel_data
        pos = int(kwargs.get(ATTR_POSITION))
        value = pos if self.is_inverted_control else 100 - pos

        _LOGGER.debug(
            "set_cover_position for cover: %s. From HA: %s, model: %s",
            self.entity_id,
            pos,
            value,
        )
        if await self.async_action(ExtaLifeAPI.ACTN_SET_POS, value=value):
            data["value"] = value
            self.async_schedule_update_ha_state()

    @property
    def is_inverted_control(self):
        return self.config_entry.options.get(DOMAIN_COVER).get(
            OPTIONS_COVER_INVERTED_CONTROL, False
        )

    @property
    def is_closed(self):
        """Return if the cover is closed (affects roller icon and entity status)."""
        position = self.channel_data.get("value")

        if position is None:
            return None
        pos = ExtaLifeCover.POS_CLOSED
        _LOGGER.debug(
            "is_closed for cover: %s. model: %s, returned to HA: %s",
            self.entity_id,
            position,
            position == pos,
        )
        return position == pos

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        data = self.channel_data
        pos = ExtaLifeCover.POS_OPEN

        if not self.is_exta_free:
            if await self.async_action(ExtaLifeAPI.ACTN_SET_POS, value=pos):
                data["value"] = pos
                _LOGGER.debug(
                    "open_cover for cover: %s. model: %s", self.entity_id, pos
                )
                self.async_schedule_update_ha_state()
        else:
            if await self.async_action(
                ExtaLifeAPI.ACTN_EXFREE_UP_PRESS
            ) and await self.async_action(ExtaLifeAPI.ACTN_EXFREE_UP_RELEASE):
                self.async_schedule_update_ha_state()

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        data = self.channel_data
        pos = ExtaLifeCover.POS_CLOSED

        if not self.is_exta_free:
            if await self.async_action(ExtaLifeAPI.ACTN_SET_POS, value=pos):
                data["value"] = pos
                _LOGGER.debug(
                    "close_cover for cover: %s. model: %s", self.entity_id, pos
                )
                self.async_schedule_update_ha_state()

        elif (
            DEVICE_MAP_TYPE_TO_MODEL.get(self.channel_data.get("type")) != MODEL_ROB01
        ):  # ROB-01 supports only 1 toggle mode using 1 command
            if await self.async_action(
                ExtaLifeAPI.ACTN_EXFREE_DOWN_PRESS
            ) and await self.async_action(ExtaLifeAPI.ACTN_EXFREE_DOWN_RELEASE):
                self.async_schedule_update_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.async_action(ExtaLifeAPI.ACTN_STOP)

    def on_state_notification(self, data):
        """ React on state notification from controller """
        ch_data = self.channel_data.copy()
        ch_data["value"] = data.get("value")

        # update only if notification data contains new status; prevent HA event bus overloading
        if ch_data != self.channel_data:
            self.channel_data.update(ch_data)

            # synchronize DataManager data with processed update & entity data
            self.sync_data_update_ha()
