"""Sensor classes for Kodi."""
from __future__ import annotations

import logging
from typing import Any

from jsonrpc_base.jsonrpc import TransportError

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .connection_manager import KodiConnectionClient, KodiConnectionManager
from .const import DATA_CONNECTION, DOMAIN, WS_DPMS, WS_SCREENSAVER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kodi sensors based on a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    connman = data[DATA_CONNECTION]
    if (uid := config_entry.unique_id) is None:
        uid = config_entry.entry_id

    sensor_entities = [
        KodiBinaryEntity(
            WS_SCREENSAVER["name"],
            WS_SCREENSAVER["on"],
            WS_SCREENSAVER["off"],
            WS_SCREENSAVER["boolean"],
            uid,
            connman,
        ),
        KodiBinaryEntity(
            WS_DPMS["name"],
            WS_DPMS["on"],
            WS_DPMS["off"],
            WS_DPMS["boolean"],
            uid,
            connman,
        ),
    ]
    async_add_entities(sensor_entities)


class KodiBinaryEntity(KodiConnectionClient, BinarySensorEntity):
    """Generic binary sensor entity for WebSocket callbacks."""

    def __init__(
        self,
        name: str,
        api_on: str,
        api_off: str,
        boolean_name: str,
        uid: str,
        connman: KodiConnectionManager,
    ) -> None:
        """Initialize kodi binary sensor."""
        # Define used websocket methods including their callbacks
        super().__init__(connman, {api_on: self.async_on, api_off: self.async_off})

        self._attr_is_on = False
        self._attr_name = name
        self._attr_unique_id = f"{uid}_{api_on}"
        self._kodi_boolean = boolean_name

    @callback
    def async_on(self, sender: Any, data: Any):  # pylint: disable=unused-argument
        """Switch sensor on from api call."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.debug("Kodi %s on", self.name)

    @callback
    def async_off(self, sender: Any, data: Any):  # pylint: disable=unused-argument
        """Switch sensor off from api call."""
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.debug("Kodi %s off", self.name)

    def _reset_state(self):
        """Set state to default."""
        self._attr_is_on = False

    async def async_update(self) -> None:
        """Retrieve boolean display properties."""
        if not self._connman.connected:
            return

        display_properties = {"booleans": [self._kodi_boolean]}
        try:
            display_status = await self._connman.kodi.call_method(
                "XBMC.GetInfoBooleans", **display_properties
            )
            # Test for invalid response from Kodi
            if display_status:
                self._attr_is_on = display_status[self._kodi_boolean]
                _LOGGER.debug(
                    "Query status for %s: %d %s",
                    self.name,
                    self._attr_is_on,
                    display_status,
                )
            else:
                _LOGGER.debug(
                    "Query status for %s is None: %d", self.name, self._attr_is_on
                )
        except TransportError:
            self._reset_state()
            _LOGGER.debug("Query status for %s failed: %d", self.name, self._attr_is_on)
