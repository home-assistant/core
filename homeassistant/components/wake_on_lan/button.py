"""Support for wake on lan buttons."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import wakeonlan

from homeassistant.components.button import PLATFORM_SCHEMA, ButtonEntity
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_MAC,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a wake on lan button."""
    broadcast_address = config.get(CONF_BROADCAST_ADDRESS)
    broadcast_port = config.get(CONF_BROADCAST_PORT)
    mac_address = config[CONF_MAC]
    name = config[CONF_NAME]

    add_entities(
        [
            WolButton(
                hass,
                name,
                mac_address,
                broadcast_address,
                broadcast_port,
            )
        ],
    )


class WolButton(ButtonEntity):
    """Representation of a wake on lan button."""

    def __init__(
        self,
        hass,
        name,
        mac_address,
        broadcast_address,
        broadcast_port,
    ):
        """Initialize the WOL button."""
        self._hass = hass
        self._name = name
        self._mac_address = mac_address
        self._broadcast_address = broadcast_address
        self._broadcast_port = broadcast_port
        self._unique_id = dr.format_mac(mac_address)
        self._attr_icon = "mdi:power"

    @property
    def name(self):
        """Return the name of the button."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this button."""
        return self._unique_id

    def press(self, **kwargs: Any) -> None:
        """Press the button."""
        service_kwargs = {}
        if self._broadcast_address is not None:
            service_kwargs["ip_address"] = self._broadcast_address
        if self._broadcast_port is not None:
            service_kwargs["port"] = self._broadcast_port

        _LOGGER.info(
            "Send magic packet to mac %s (broadcast: %s, port: %s)",
            self._mac_address,
            self._broadcast_address,
            self._broadcast_port,
        )

        wakeonlan.send_magic_packet(self._mac_address, **service_kwargs)
