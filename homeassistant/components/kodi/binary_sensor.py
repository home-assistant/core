"""Sensor classes for kodi."""
from __future__ import annotations

import logging

from jsonrpc_base.jsonrpc import TransportError

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CONNECTION, DOMAIN

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


class KodiBinaryEntity(BinarySensorEntity):
    """Generic binary sensor entity for WebSocket callbacks."""

    _attr_has_entity_name = True

    def __init__(self, name, api_on, api_off, boolean, uid, connman):
        """Initialize kodi binary sensor."""
        self._is_on = False
        self._attr_name = name
        self._attr_unique_id = uid + "_" + api_on
        self._api_on = api_on
        self._api_off = api_off
        self._kodi_boolean = boolean
        self._connman = connman
        self._kodi_uid = uid

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._is_on

    @property
    def device_info(self):
        """Return kodi uid to register entity with the kodi device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._kodi_uid)},
        )

    @callback
    def async_on(self, sender, data):  # pylint: disable=unused-argument
        """Switch sensor on from api call."""
        self._is_on = True
        self.async_write_ha_state()
        _LOGGER.debug("Kodi %s on (%s)", self.name, self._api_on)

    @callback
    def async_off(self, sender, data):  # pylint: disable=unused-argument
        """Switch sensor off from api call."""
        self._is_on = False
        self.async_write_ha_state()
        _LOGGER.debug("Kodi %s off (%s)", self.name, self._api_off)

    @callback
    def async_dummy(self, sender, data):
        """Empty function to replace websocket callbacks on lost/closed connection."""

    async def async_added_to_hass(self) -> None:
        """Register callbacks for needed api endpoints."""
        await self._connman.add_callback_on_connect(self._on_ws_connected)
        await self._connman.add_callback_on_disconnect(self._on_ws_disconnected)

    @callback
    async def _on_ws_connected(self):
        """Call after ws is connected."""
        _LOGGER.debug("Binary sensor %s websocket connected", self.name)
        await self.async_query_display_status()
        await self._register_ws_callbacks()

    @callback
    async def _on_ws_disconnected(self):
        """Call after ws is connected."""
        await self._unregister_ws_callbacks()
        await self._clear_connection()

    @callback
    async def _register_ws_callbacks(self):
        """Register kodi websocked callbacks for this sensor."""
        _LOGGER.debug("Setting up binary sensor callbacks for Kodi %s", self.name)
        server = self._connman.connection.server
        setattr(server, self._api_on, self.async_on)
        setattr(server, self._api_off, self.async_off)

    @callback
    async def _unregister_ws_callbacks(self):
        """Register kodi websocked callbacks for this sensor."""
        _LOGGER.debug("Removing binary sensor callbacks for %s", self.name)
        server = self._connman.connection.server
        setattr(server, self._api_on, self.async_dummy)
        setattr(server, self._api_off, self.async_dummy)

    async def async_query_display_status(self):
        """Retrieve boolean Kodi display properties."""
        display_properties = {"booleans": [self._kodi_boolean]}
        display_status = await self._connman.kodi.call_method(
            "XBMC.GetInfoBooleans", **display_properties
        )
        self._is_on = display_status[self._kodi_boolean]
        _LOGGER.debug("Query statue: %d %s", self._is_on, display_status)
        self.async_write_ha_state()

    async def _clear_connection(self):
        _LOGGER.debug("Binary sensor %s clear connection", self.name)
        self._reset_state()
        self.async_write_ha_state()

    def _reset_state(self):
        """Set state to default."""
        self._is_on = False

    async def async_update(self) -> None:
        """Retrieve latest state."""
        if not self._connman.connected:
            self._reset_state()
            return

        try:
            await self.async_query_display_status()
        except TransportError:
            self._reset_state()
            return

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return not self._connman.can_subscribe
