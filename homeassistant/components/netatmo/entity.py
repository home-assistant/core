"""Base class for Netatmo entities."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pyatmo import DeviceType, Home, Room
from pyatmo.modules.base_class import NetatmoBase
from pyatmo.modules.device_types import (
    DEVICE_DESCRIPTION_MAP,
    DeviceType as NetatmoDeviceType,
)

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_URL_ENERGY,
    DATA_DEVICE_IDS,
    DEFAULT_ATTRIBUTION,
    DOMAIN,
    SIGNAL_NAME,
)
from .data_handler import PUBLIC, NetatmoDataHandler, NetatmoRoom


class NetatmoBaseEntity(Entity):
    """Netatmo entity base class."""

    _attr_attribution = DEFAULT_ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, data_handler: NetatmoDataHandler, device: NetatmoBase) -> None:
        """Set up Netatmo entity base."""
        self.data_handler = data_handler
        self.device = device
        self._publishers: list[dict[str, Any]] = []
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        for publisher in self._publishers:
            signal_name = publisher[SIGNAL_NAME]

            if "home_id" in publisher:
                await self.data_handler.subscribe(
                    publisher["name"],
                    signal_name,
                    self.async_update_callback,
                    home_id=publisher["home_id"],
                )

            elif publisher["name"] == PUBLIC:
                await self.data_handler.subscribe(
                    publisher["name"],
                    signal_name,
                    self.async_update_callback,
                    lat_ne=publisher["lat_ne"],
                    lon_ne=publisher["lon_ne"],
                    lat_sw=publisher["lat_sw"],
                    lon_sw=publisher["lon_sw"],
                )

            else:
                await self.data_handler.subscribe(
                    publisher["name"], signal_name, self.async_update_callback
                )

            if any(
                sub is None
                for sub in self.data_handler.publisher[signal_name].subscriptions
            ):
                await self.data_handler.unsubscribe(signal_name, None)

        self.async_update_callback()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()

        for publisher in self._publishers:
            await self.data_handler.unsubscribe(
                publisher[SIGNAL_NAME], self.async_update_callback
            )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        raise NotImplementedError

    @property
    @abstractmethod
    def device_type(self) -> DeviceType:
        """Return the device type."""

    @property
    def device_description(self) -> tuple[str, str]:
        """Return the model of this device."""
        if "." in self.device_type:
            netatmo_device = NetatmoDeviceType(self.device_type.partition(".")[2])
        else:
            netatmo_device = getattr(NetatmoDeviceType, self.device_type)
        return DEVICE_DESCRIPTION_MAP[netatmo_device]


class NetatmoRoomEntity(NetatmoBaseEntity):
    """Netatmo room entity base class."""

    device: Room

    def __init__(self, room: NetatmoRoom) -> None:
        """Set up a Netatmo room entity."""
        super().__init__(room.data_handler, room.room)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, room.room.entity_id)},
            name=room.room.name,
            manufacturer=self.device_description[0],
            model=self.device_description[1],
            configuration_url=CONF_URL_ENERGY,
            suggested_area=room.room.name,
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        registry = dr.async_get(self.hass)
        if device := registry.async_get_device(
            identifiers={(DOMAIN, self.device.entity_id)}
        ):
            self.hass.data[DOMAIN][DATA_DEVICE_IDS][self.device.entity_id] = device.id

    @property
    def device_type(self) -> DeviceType:
        """Return the device type."""
        assert self.device.climate_type
        return self.device.climate_type

    @property
    def home(self) -> Home:
        """Return the home this room belongs to."""
        return self.device.home
