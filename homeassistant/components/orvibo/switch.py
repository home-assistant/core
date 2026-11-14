"""Switch platform for the Orvibo integration."""

import logging
from typing import Any, override

from orvibo.s20 import S20, S20Exception

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .models import S20ConfigEntry

_LOGGER = logging.getLogger(__name__)

DEFAULT_DISCOVERY = False

# Library is not thread safe and uses global variables,
# so we limit to 1 update at a time
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S20ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up orvibo from a config entry."""
    async_add_entities(
        [
            S20Switch(
                entry.title,
                entry.data[CONF_HOST],
                entry.data[CONF_MAC],
                entry.runtime_data,
            )
        ]
    )


class S20Switch(SwitchEntity):
    """Representation of an S20 switch."""

    _attr_has_entity_name = True

    def __init__(self, name: str, host: str, mac: str, s20: S20) -> None:
        """Initialize the S20 device."""

        self._attr_is_on = False
        self._host = host
        self._mac = mac
        self._s20 = s20
        self._attr_unique_id = self._mac
        self._name = name
        self._attr_name = None
        self._attr_device_info = DeviceInfo(
            identifiers={
                # MAC addresses are used as unique identifiers within this domain
                (DOMAIN, self._attr_unique_id)
            },
            name=name,
            manufacturer="Orvibo",
            model="S20",
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
        )

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        try:
            self._s20.on = True
        except S20Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_on_error",
                translation_placeholders={"name": self._name},
            ) from err

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        try:
            self._s20.on = False
        except S20Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_error",
                translation_placeholders={"name": self._name},
            ) from err

    def update(self) -> None:
        """Update device state."""
        try:
            self._attr_is_on = self._s20.on

            # If the device was previously offline, let the user know it's back!
            if not self._attr_available:
                _LOGGER.info("Orvibo switch %s reconnected", self._name)
                self._attr_available = True

        except S20Exception as err:
            # Only log the error if this is the FIRST time it failed
            if self._attr_available:
                _LOGGER.info(
                    "Error communicating with Orvibo switch %s: %s", self._name, err
                )
                self._attr_available = False
