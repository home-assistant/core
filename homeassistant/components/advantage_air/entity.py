"""Advantage Air parent entity class."""
from typing import Any

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class AdvantageAirEntity(CoordinatorEntity):
    """Parent class for Advantage Air Entities."""

    _attr_has_entity_name = True

    def __init__(self, instance):
        """Initialize common aspects of an Advantage Air entity."""
        super().__init__(instance["coordinator"])
        self._attr_unique_id = self.coordinator.data["system"]["rid"]


class AdvantageAirAcEntity(AdvantageAirEntity):
    """Parent class for Advantage Air AC Entities."""

    def __init__(self, instance, ac_key):
        """Initialize common aspects of an Advantage Air ac entity."""
        super().__init__(instance)
        self.aircon = instance["aircon"]
        self.ac_key = ac_key
        self._attr_unique_id += f"-{ac_key}"

        self._attr_device_info = DeviceInfo(
            via_device=(DOMAIN, self.coordinator.data["system"]["rid"]),
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Advantage Air",
            model=self.coordinator.data["system"]["sysType"],
            name=self.coordinator.data["aircons"][self.ac_key]["info"]["name"],
        )

    @property
    def _ac(self):
        return self.coordinator.data["aircons"][self.ac_key]["info"]


class AdvantageAirZoneEntity(AdvantageAirAcEntity):
    """Parent class for Advantage Air Zone Entities."""

    def __init__(self, instance, ac_key, zone_key):
        """Initialize common aspects of an Advantage Air zone entity."""
        super().__init__(instance, ac_key)
        self.zone_key = zone_key
        self._attr_unique_id += f"-{zone_key}"

    @property
    def _zone(self):
        return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key]


class AdvantageAirThingEntity(AdvantageAirEntity):
    """Parent class for Advantage Air Things Entities."""

    def __init__(self, instance, thing):
        """Initialize common aspects of an Advantage Air Things entity."""
        super().__init__(instance)
        self.async_change = instance["things"]
        self._id = thing["id"]
        self._attr_unique_id += f"-{self._id}"

        self._attr_device_info = DeviceInfo(
            via_device=(DOMAIN, self.coordinator.data["system"]["rid"]),
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Advantage Air",
            model="MyPlace",
            name=thing["name"],
        )

    @property
    def _data(self):
        """Return the thing data."""
        return self.coordinator.data["myThings"]["things"][self._id]

    @property
    def is_on(self):
        """Return if the thing is considered on."""
        return self._data["value"] > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the thing on."""
        await self.async_change({"id": self._id, "value": 100})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the thing off."""
        await self.async_change({"id": self._id, "value": 0})
