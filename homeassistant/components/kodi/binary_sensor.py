"""Sensor classes for kodi."""
from __future__ import annotations

import logging

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
    connection = data[DATA_CONNECTION]
    if (uid := config_entry.unique_id) is None:
        uid = config_entry.entry_id

    _LOGGER.error("Kodi Sensor, Aufstellen!")

    sensor_entities = [
        KodiBinaryEntity(
            "Screensaver",
            "GUI.OnScreensaverActivated",
            "GUI.OnScreensaverDeactivated",
            uid,
            connection,
        ),
        KodiBinaryEntity(
            "Energy saving",
            "GUI.OnDPMSActivated",
            "GUI.OnDPMSDeactivated",
            uid,
            connection,
        ),
    ]
    async_add_entities(sensor_entities)


class KodiBinaryEntity(BinarySensorEntity):
    """Generic binary sensor entity for WebSocket callbacks."""

    _attr_has_entity_name = True

    def __init__(self, name, api_on, api_off, uid, connection):
        """Initialize kodi binary sensor."""
        self._is_on = False
        self._attr_name = name
        self._attr_unique_id = uid + "_" + api_on
        self._api_on = api_on
        self._api_off = api_off
        self._connection = connection
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

    @callback
    def async_off(self, sender, data):  # pylint: disable=unused-argument
        """Switch sensor off from api call."""
        self._is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks for needed api endpoints."""
        setattr(self._connection.server, self._api_on, self.async_on)
        setattr(self._connection.server, self._api_off, self.async_off)
