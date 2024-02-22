"""Base entity Ambient Weather Station Service."""
from __future__ import annotations

from aioambient.util import get_public_device_id

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from . import AmbientStation
from .const import ATTR_LAST_DATA, DOMAIN, TYPE_SOLARRADIATION, TYPE_SOLARRADIATION_LX


class AmbientWeatherEntity(Entity):
    """Define a base Ambient PWS entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        ambient: AmbientStation,
        mac_address: str,
        station_name: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        self._ambient = ambient

        public_device_id = get_public_device_id(mac_address)
        self._attr_device_info = DeviceInfo(
            configuration_url=(
                f"https://ambientweather.net/dashboard/{public_device_id}"
            ),
            identifiers={(DOMAIN, mac_address)},
            manufacturer="Ambient Weather",
            name=station_name.capitalize(),
        )

        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._mac_address = mac_address
        self.entity_description = description

    @callback
    def _async_update(self) -> None:
        """Update the state."""
        last_data = self._ambient.stations[self._mac_address][ATTR_LAST_DATA]
        key = self.entity_description.key
        available_key = TYPE_SOLARRADIATION if key == TYPE_SOLARRADIATION_LX else key
        self._attr_available = last_data[available_key] is not None
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"ambient_station_data_update_{self._mac_address}",
                self._async_update,
            )
        )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError
