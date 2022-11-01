"""Sensor classes for Kodi."""
from __future__ import annotations

import logging

from jsonrpc_base.jsonrpc import TransportError

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
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
        super().__init__(connman)
        self._attr_is_on = False
        self._attr_name = name
        self._attr_unique_id = uid + "_" + api_on
        self._api_on = api_on
        self._api_off = api_off
        self._kodi_boolean = boolean_name
        self._kodi_uid = uid
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._kodi_uid)},
        )

    @callback
    def async_on(self, sender, data):  # pylint: disable=unused-argument
        """Switch sensor on from api call."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.debug("Kodi %s on (%s)", self.name, self._api_on)

    @callback
    def async_off(self, sender, data):  # pylint: disable=unused-argument
        """Switch sensor off from api call."""
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.debug("Kodi %s off (%s)", self.name, self._api_off)

    async def async_added_to_hass(self) -> None:
        """Register callbacks for needed api endpoints."""
        await self._connman.add_callback_on_connect(self._on_ws_connected)
        await self._connman.add_callback_on_disconnect(self._on_ws_disconnected)

    @callback
    async def _on_ws_connected(self):
        """Call after websocket is connected."""
        _LOGGER.debug("Binary sensor %s websocket connected", self.name)
        await self._async_query_booleans()
        await self._register_ws_callbacks()

    @callback
    async def _on_ws_disconnected(self):
        """Call after websocket is connected."""
        await self._unregister_ws_callbacks()
        await self._clear_connection()

    @callback
    async def _register_ws_callbacks(self):
        """Register Kodi websocked callbacks for this sensor."""
        _LOGGER.debug("Setting up binary sensor callbacks for Kodi %s", self.name)
        self._connman.register_websocket_callback(self._api_on, self.async_on)
        self._connman.register_websocket_callback(self._api_off, self.async_off)

    @callback
    async def _unregister_ws_callbacks(self):
        """Register Kodi websocked callbacks for this sensor."""
        _LOGGER.debug("Removing binary sensor callbacks for %s", self.name)
        self._connman.unregister_websocket_callback(self._api_on)
        self._connman.unregister_websocket_callback(self._api_off)

    async def _async_query_booleans(self):
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
                _LOGGER.debug("Query status: %d %s", self._attr_is_on, display_status)
                self.async_write_ha_state()
            else:
                _LOGGER.debug(
                    "Query status None: %d %s", self._attr_is_on, display_status
                )
        except TransportError:
            _LOGGER.debug(
                "Query status failed: %d %s", self._attr_is_on, display_status
            )

    async def _clear_connection(self):
        _LOGGER.debug("Binary sensor %s clear connection", self.name)
        self._reset_state()
        self.async_write_ha_state()

    def _reset_state(self):
        """Set state to default."""
        self._attr_is_on = False

    async def async_update(self) -> None:
        """Retrieve latest state."""
        if not self._connman.connected:
            self._reset_state()
            return

        try:
            await self._async_query_booleans()
        except TransportError:
            self._reset_state()
            return
