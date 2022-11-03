"""Sensor classes for Kodi."""
from __future__ import annotations

import logging

from jsonrpc_base.jsonrpc import TransportError

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CONNECTION, DOMAIN
from .kodi_connman import KodiConnectionClient, KodiConnectionManager

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
            "Screensaver",
            "GUI.OnScreensaverActivated",
            "GUI.OnScreensaverDeactivated",
            "System.ScreenSaverActive",
            uid,
            connman,
        ),
        KodiBinaryEntity(
            "Energy saving",
            "GUI.OnDPMSActivated",
            "GUI.OnDPMSDeactivated",
            "System.DPMSActive",
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
        self._websocket_callbacks = {api_on: self.async_on, api_off: self.async_off}
        super().__init__(connman)

        self._attr_is_on = False
        self._attr_name = name
        self._attr_unique_id = f"{uid}_{api_on}"
        self._kodi_boolean = boolean_name

    @callback
    def async_on(self, sender, data):  # pylint: disable=unused-argument
        """Switch sensor on from api call."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.debug("Kodi %s on", self.name)

    @callback
    def async_off(self, sender, data):  # pylint: disable=unused-argument
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
                self.async_write_ha_state()
            else:
                _LOGGER.debug(
                    "Query status for %s is None: %d", self.name, self._attr_is_on
                )
        except TransportError:
            self._reset_state()
            _LOGGER.debug("Query status for %s failed: %d", self.name, self._attr_is_on)
