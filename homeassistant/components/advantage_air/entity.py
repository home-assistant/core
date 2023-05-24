"""Advantage Air parent entity class."""
from typing import Any

from advantage_air import ApiError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .models import AdvantageAirData


class AdvantageAirEntity(CoordinatorEntity):
    """Parent class for Advantage Air Entities."""

    _attr_has_entity_name = True

    def __init__(self, instance: AdvantageAirData) -> None:
        """Initialize common aspects of an Advantage Air entity."""
        super().__init__(instance.coordinator)
        self._attr_unique_id: str = self.coordinator.data["system"]["rid"]

    def update_handle_factory(self, func, *keys):
        """Return the provided API function wrapped.

        Adds an error handler and coordinator refresh, and presets keys.
        """

        async def update_handle(*values):
            try:
                if await func(*keys, *values):
                    await self.coordinator.async_refresh()
            except ApiError as err:
                raise HomeAssistantError(err) from err

        return update_handle


class AdvantageAirAcEntity(AdvantageAirEntity):
    """Parent class for Advantage Air AC Entities."""

    def __init__(self, instance: AdvantageAirData, ac_key: str) -> None:
        """Initialize common aspects of an Advantage Air ac entity."""
        super().__init__(instance)

        self.ac_key: str = ac_key
        self._attr_unique_id += f"-{ac_key}"

        self._attr_device_info = DeviceInfo(
            via_device=(DOMAIN, self.coordinator.data["system"]["rid"]),
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Advantage Air",
            model=self.coordinator.data["system"]["sysType"],
            name=self.coordinator.data["aircons"][self.ac_key]["info"]["name"],
        )
        self.async_update_ac = self.update_handle_factory(
            instance.api.aircon.async_update_ac, self.ac_key
        )

    @property
    def _ac(self) -> dict[str, Any]:
        return self.coordinator.data["aircons"][self.ac_key]["info"]


class AdvantageAirZoneEntity(AdvantageAirAcEntity):
    """Parent class for Advantage Air Zone Entities."""

    def __init__(self, instance: AdvantageAirData, ac_key: str, zone_key: str) -> None:
        """Initialize common aspects of an Advantage Air zone entity."""
        super().__init__(instance, ac_key)

        self.zone_key: str = zone_key
        self._attr_unique_id += f"-{zone_key}"
        self.async_update_zone = self.update_handle_factory(
            instance.api.aircon.async_update_zone, self.ac_key, self.zone_key
        )

    @property
    def _zone(self) -> dict[str, Any]:
        return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key]


class AdvantageAirThingEntity(AdvantageAirEntity):
    """Parent class for Advantage Air Things Entities."""

    def __init__(self, instance: AdvantageAirData, thing: dict[str, Any]) -> None:
        """Initialize common aspects of an Advantage Air Things entity."""
        super().__init__(instance)

        self._id = thing["id"]
        self._attr_unique_id += f"-{self._id}"

        self._attr_device_info = DeviceInfo(
            via_device=(DOMAIN, self.coordinator.data["system"]["rid"]),
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Advantage Air",
            model="MyPlace",
            name=thing["name"],
        )
        self.async_update_value = self.update_handle_factory(
            instance.api.things.async_update_value, self._id
        )

    @property
    def _data(self) -> dict:
        """Return the thing data."""
        return self.coordinator.data["myThings"]["things"][self._id]

    @property
    def is_on(self):
        """Return if the thing is considered on."""
        return self._data["value"] > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the thing on."""
        await self.async_update_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the thing off."""
        await self.async_update_value(False)
