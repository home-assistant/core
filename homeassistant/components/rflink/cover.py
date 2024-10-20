"""Support for Rflink Cover devices."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverEntity,
    CoverState,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ALIASES,
    CONF_DEVICE_DEFAULTS,
    CONF_FIRE_EVENT,
    CONF_GROUP,
    CONF_GROUP_ALIASES,
    CONF_NOGROUP_ALIASES,
    CONF_SIGNAL_REPETITIONS,
    DEVICE_DEFAULTS_SCHEMA,
)
from .entity import RflinkCommand

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

TYPE_STANDARD = "standard"
TYPE_INVERTED = "inverted"

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Rflink cover platform."""
    async_add_entities(devices_from_config(config))


class RflinkCover(RflinkCommand, CoverEntity, RestoreEntity):
    """Rflink entity which can switch on/stop/off (eg: cover)."""

    async def async_added_to_hass(self) -> None:
        """Restore RFLink cover state (OPEN/CLOSE)."""
        await super().async_added_to_hass()
        if (old_state := await self.async_get_last_state()) is not None:
            self._state = old_state.state == CoverState.OPEN

    def _handle_event(self, event):
        """Adjust state if Rflink picks up a remote command for this device."""
        self.cancel_queued_send_commands()

        command = event["command"]
        if command in ["on", "allon", "up"]:
            self._state = True
        elif command in ["off", "alloff", "down"]:
            self._state = False

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return not self._state

    @property
    def assumed_state(self) -> bool:
        """Return True because covers can be stopped midway."""
        return True

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Turn the device close."""
        await self._async_handle_command("close_cover")

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Turn the device open."""
        await self._async_handle_command("open_cover")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Turn the device stop."""
        await self._async_handle_command("stop_cover")


class InvertedRflinkCover(RflinkCover):
    """Rflink cover that has inverted open/close commands."""

    async def _async_send_command(self, cmd, repetitions):
        """Will invert only the UP/DOWN commands."""
        _LOGGER.debug("Getting command: %s for Rflink device: %s", cmd, self._device_id)
        cmd_inv = {"UP": "DOWN", "DOWN": "UP"}
        await super()._async_send_command(cmd_inv.get(cmd, cmd), repetitions)
