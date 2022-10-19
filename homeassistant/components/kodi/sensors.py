"""Sensor classes for kodi."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


class KodiBinaryEntity(BinarySensorEntity):
    """Generic binary sensor entity for WebSocket callbacks."""

    _attr_has_entity_name = True

    def __init__(self, name, api_on, api_off, uid):
        """Initialize kodi binary sensor."""
        self._is_on = False
        self._attr_name = name
        self._attr_unique_id = uid + "_" + api_on
        self._kodi_uid = uid
        self._api_on = api_on
        self._api_off = api_off

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

    def register_callbacks(self, connection):
        """Register api endpoints to states on and off."""
        setattr(connection.server, self._api_on, self.async_on)
        setattr(connection.server, self._api_off, self.async_off)

    def reset_state(self):
        """Reset sensor to default."""
        self._is_on = False
        # async_write_ha_state is done by the kodi entity
