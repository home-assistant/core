"""Support for Rflink Cover devices."""
import logging
import time
from typing import Callable, Optional

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    PLATFORM_SCHEMA,
    CoverEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_TYPE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    CONF_ALIASES,
    CONF_DEVICE_DEFAULTS,
    CONF_FIRE_EVENT,
    CONF_GROUP,
    CONF_GROUP_ALIASES,
    CONF_NOGROUP_ALIASES,
    CONF_SIGNAL_REPETITIONS,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_TRAVELLING_TIME_UP,
    DEFAULT_TRAVEL_TIME,
    DEVICE_DEFAULTS_SCHEMA,
    RflinkCommand,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

TYPE_STANDARD = "standard"
TYPE_INVERTED = "inverted"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})
        ): DEVICE_DEFAULTS_SCHEMA,
        vol.Optional(CONF_DEVICES, default={}): vol.Schema(
            {
                cv.string: {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_TYPE): vol.Any(TYPE_STANDARD, TYPE_INVERTED),
                    vol.Optional(CONF_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_GROUP_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_NOGROUP_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
                    vol.Optional(CONF_SIGNAL_REPETITIONS): vol.Coerce(int),
                    vol.Optional(CONF_GROUP, default=True): cv.boolean,
                    vol.Optional(
                        CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME
                    ): cv.positive_float,
                    vol.Optional(
                        CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME
                    ): cv.positive_float,
                }
            }
        ),
    }
)


def entity_type_for_device_id(device_id):
    """Return entity class for protocol of a given device_id.

    Async friendly.
    """
    entity_type_mapping = {
        # KlikAanKlikUit cover have the controls inverted
        "newkaku": TYPE_INVERTED
    }
    protocol = device_id.split("_")[0]
    return entity_type_mapping.get(protocol, TYPE_STANDARD)


def entity_class_for_type(entity_type):
    """Translate entity type to entity class.

    Async friendly.
    """
    entity_device_mapping = {
        # default cover implementation
        TYPE_STANDARD: RflinkCover,
        # cover with open/close commands inverted
        # like KAKU/COCO ASUN-650
        TYPE_INVERTED: InvertedRflinkCover,
    }

    return entity_device_mapping.get(entity_type, RflinkCover)


def devices_from_config(domain_config):
    """Parse configuration and add Rflink cover devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        # Determine what kind of entity to create, RflinkCover
        # or InvertedRflinkCover
        if CONF_TYPE in config:
            # Remove type from config to not pass it as and argument
            # to entity instantiation
            entity_type = config.pop(CONF_TYPE)
        else:
            entity_type = entity_type_for_device_id(device_id)

        entity_class = entity_class_for_type(entity_type)
        device_config = dict(domain_config[CONF_DEVICE_DEFAULTS], **config)
        device = entity_class(device_id, **device_config)
        devices.append(device)

    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Rflink cover platform."""
    async_add_entities(devices_from_config(config))


class RflinkCover(RflinkCommand, CoverEntity, RestoreEntity):
    """Rflink entity which can switch on/stop/off (eg: cover)."""

    _attr_current_cover_position = 0
    _attr_assumed_state = True
    _cancel: Optional[Callable] = None
    _last_cover_position = None
    _motion_start_time = None

    def __init__(self, device_id, travelling_time_up, travelling_time_down, **kwargs):
        """Handle cover specific args and super init."""
        super().__init__(device_id, **kwargs)
        self._opening_time = travelling_time_up
        self._closing_time = travelling_time_down

    async def async_added_to_hass(self):
        """Restore RFLink cover state (OPEN/CLOSE)."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._attr_current_cover_position = old_state.attributes.get(
                ATTR_CURRENT_POSITION, 0
            )

    def _handle_event(self, event):
        """Adjust state if Rflink picks up a remote command for this device."""
        self.cancel_queued_send_commands()

        command = event["command"]
        if command in ["on", "allon", "up"]:
            self._start_motion(100, True)
        elif command in ["off", "alloff", "down"]:
            self._start_motion(0, False)
        elif command in ["stop", "allstop"]:
            self._cancel_job()
            self._calc_new_pos()
            self._stopped()

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._attr_current_cover_position == 0

    async def async_close_cover(self, **kwargs):
        """Turn the device close."""
        await self.async_set_cover_position(position=0)

    async def async_open_cover(self, **kwargs):
        """Turn the device open."""
        await self.async_set_cover_position(position=100)

    async def async_stop_cover(self, **kwargs):
        """Turn the device stop."""
        self._cancel_job()
        self._calc_new_pos()
        await self._async_handle_command("stop_cover")
        self._stopped()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            new_position = kwargs[ATTR_POSITION]
            current_position = self.current_cover_position

            _LOGGER.info("set_pos %s -> %s", current_position, new_position)
            if new_position < current_position or new_position == 0:
                self._start_motion(new_position, False)
                await self._async_handle_command("close_cover")

            if new_position > current_position or new_position == 100:
                self._start_motion(new_position, True)
                await self._async_handle_command("open_cover")

    def _start_motion(self, new_position, is_opening):
        self._cancel_job()

        self._last_cover_position = self._attr_current_cover_position
        self._attr_current_cover_position = new_position

        sleep_time = self._get_traveling_time(self._last_cover_position, new_position)
        if sleep_time:
            self._attr_is_opening = is_opening
            self._attr_is_closing = not is_opening
            self._motion_start_time = time.time()
            self._cancel = async_call_later(self.hass, sleep_time, self._auto_stop)
        self.schedule_update_ha_state()

    def _get_traveling_time(self, current_position, new_position):
        if current_position > new_position:
            return self._closing_time / 100.0 * (current_position - new_position)

        if current_position < new_position:
            return self._opening_time / 100.0 * (new_position - current_position)
        return 0

    async def _auto_stop(self, now=None):
        self._cancel = None
        if 0 < self._attr_current_cover_position < 100:
            await self._async_handle_command("stop_cover")
        self._stopped()

    def _cancel_job(self):
        if self._cancel:
            _LOGGER.info("cancel delayed job")
            self._cancel()
            self._cancel = None

    def _stopped(self):
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._motion_start_time = None
        self.schedule_update_ha_state()

    def _calc_new_pos(self):
        if self._motion_start_time is None or self._last_cover_position is None:
            return

        moving_time = self._opening_time if self.is_opening else self._closing_time
        travelled = (time.time() - self._motion_start_time) / moving_time * 100
        if not self.is_opening:
            travelled = -travelled
        position = int(self._last_cover_position + travelled)
        self._attr_current_cover_position = min(100, max(0, position))


class InvertedRflinkCover(RflinkCover):
    """Rflink cover that has inverted open/close commands."""

    async def _async_send_command(self, cmd, repetitions):
        """Will invert only the UP/DOWN commands."""
        _LOGGER.debug("Getting command: %s for Rflink device: %s", cmd, self._device_id)
        cmd_inv = {"UP": "DOWN", "DOWN": "UP"}
        await super()._async_send_command(cmd_inv.get(cmd, cmd), repetitions)
