"""Advantage Air parent entity class."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ADVANTAGE_AIR_AIRCONS,
    ADVANTAGE_AIR_COORDINATOR,
    ADVANTAGE_AIR_SET_AIRCON,
    DOMAIN,
)


class AdvantageAirEntity(CoordinatorEntity):
    """Parent class for all Advantage Air entities."""

    _attr_has_entity_name = True

    def __init__(self, instance):
        """Initialize common aspects of an Advantage Air entity."""
        super().__init__(instance[ADVANTAGE_AIR_COORDINATOR])


class AdvantageAirAirconEntity(AdvantageAirEntity):
    """Parent class for Advantage Air Aircon entities."""

    def __init__(self, instance, ac_key, zone_key=None):
        """Initialize common aspects of an Advantage Air Aircon entity."""
        super().__init__(instance)
        self.async_set_aircon = instance[ADVANTAGE_AIR_SET_AIRCON]
        self.ac_key = ac_key
        self.zone_key = zone_key
        self._attr_device_info = DeviceInfo(
            via_device=(DOMAIN, self.coordinator.data["system"]["rid"]),
            identifiers={
                (DOMAIN, f"{self.coordinator.data['system']['rid']}_{ac_key}")
            },
            manufacturer="Advantage Air",
            model=self.coordinator.data["system"]["sysType"],
            name=self._ac["name"],
        )

    @property
    def _ac(self):
        return self.coordinator.data[ADVANTAGE_AIR_AIRCONS][self.ac_key]["info"]

    @property
    def _zone(self):
        return self.coordinator.data[ADVANTAGE_AIR_AIRCONS][self.ac_key]["zones"][
            self.zone_key
        ]
