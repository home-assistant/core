"""Base class for Netatmo entities."""

from abc import abstractmethod
from typing import Any, cast, override

from pyatmo import DeviceType, Home, Module, Room
from pyatmo.modules.base_class import NetatmoBase, Place
from pyatmo.modules.device_types import DEVICE_DESCRIPTION_MAP

from homeassistant.const import EntityStateAttribute
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_URL_ENERGY,
    CONF_URL_WEATHER,
    DEFAULT_ATTRIBUTION,
    DOMAIN,
    SIGNAL_NAME,
)
from .coordinator import PUBLIC, NetatmoDataHandler, NetatmoDevice, NetatmoRoom


class NetatmoBaseEntity(Entity):
    """Netatmo entity base class."""

    _attr_attribution = DEFAULT_ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, data_handler: NetatmoDataHandler) -> None:
        """Set up Netatmo entity base."""
        self.data_handler = data_handler
        self._publishers: list[dict[str, Any]] = []
        self._attr_extra_state_attributes = {}

    @property
    @override
    def available(self) -> bool:
        """Return True if the underlying data publishers are reachable."""
        return super().available and all(
            self.data_handler.is_signal_available(publisher[SIGNAL_NAME])
            for publisher in self._publishers
        )

    @override
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

    @override
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


class NetatmoDeviceEntity(NetatmoBaseEntity):
    """Netatmo entity base class."""

    def __init__(
        self, data_handler: NetatmoDataHandler, device: NetatmoBase, **kwargs: Any
    ) -> None:
        """Set up Netatmo entity base."""
        super().__init__(data_handler, **kwargs)
        self.device = device

    @property
    @abstractmethod
    def device_type(self) -> DeviceType:
        """Return the device type."""

    @property
    def device_description(self) -> tuple[str, str]:
        """Return the model of this device."""
        return DEVICE_DESCRIPTION_MAP[self.device_type]

    @property
    def home(self) -> Home:
        """Return the home this room belongs to."""
        return self.device.home


class NetatmoRoomEntity(NetatmoDeviceEntity):
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

    @override
    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        registry = dr.async_get(self.hass)
        if device := registry.async_get_device(
            identifiers={(DOMAIN, self.device.entity_id)}
        ):
            self.data_handler.device_ids[self.device.entity_id] = device.id

    @property
    @override
    def device_type(self) -> DeviceType:
        """Return the device type."""
        assert self.device.climate_type
        return self.device.climate_type


class NetatmoModuleEntity(NetatmoDeviceEntity):
    """Netatmo module entity base class."""

    device: Module
    _attr_configuration_url: str

    def __init__(self, device: NetatmoDevice, **kwargs: Any) -> None:
        """Set up a Netatmo module entity."""
        super().__init__(device.data_handler, device.device, **kwargs)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device.entity_id)},
            name=device.device.name,
            manufacturer=self.device_description[0],
            model=self.device_description[1],
            configuration_url=self._attr_configuration_url,
        )

    @property
    @override
    def device_type(self) -> DeviceType:
        """Return the device type."""
        return self.device.device_type


class NetatmoReachabilityEntity(NetatmoModuleEntity):
    """Module entity that is unavailable when its device is unreachable."""

    @property
    @override
    def available(self) -> bool:
        """Return True unless the device explicitly reports as unreachable."""
        return super().available and self.device.reachable is not False


class NetatmoWeatherModuleEntity(NetatmoModuleEntity):
    """Netatmo weather module entity base class."""

    _attr_configuration_url = CONF_URL_WEATHER

    def __init__(self, device: NetatmoDevice, **kwargs: Any) -> None:
        """Set up a Netatmo weather module entity."""
        super().__init__(device, **kwargs)
        assert self.device.device_category
        category = self.device.device_category.name
        self._publishers.extend(
            [
                {
                    "name": category,
                    SIGNAL_NAME: category,
                },
            ]
        )

        if hasattr(self.device, "place"):
            place = cast(Place, self.device.place)
            if hasattr(place, "location") and place.location is not None:
                self._attr_extra_state_attributes.update(
                    {
                        EntityStateAttribute.LATITUDE: place.location.latitude,
                        EntityStateAttribute.LONGITUDE: place.location.longitude,
                    }
                )

    @property
    @override
    def device_type(self) -> DeviceType:
        """Return the Netatmo device type."""
        if "." not in self.device.device_type:
            return super().device_type
        return DeviceType(self.device.device_type.partition(".")[2])
