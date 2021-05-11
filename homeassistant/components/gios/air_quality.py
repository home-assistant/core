"""Support for the GIOS service."""
from __future__ import annotations

from typing import Any, Optional, cast

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GiosDataUpdateCoordinator
from .const import (
    API_AQI,
    API_CO,
    API_NO2,
    API_O3,
    API_PM10,
    API_PM25,
    API_SO2,
    ATTR_STATION,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    ICONS_MAP,
    MANUFACTURER,
    SENSOR_MAP,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a GIOS entities from a config_entry."""
    name = entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # We used to use int as entity unique_id, convert this to str.
    entity_registry = await async_get_registry(hass)
    old_entity_id = entity_registry.async_get_entity_id(
        "air_quality", DOMAIN, coordinator.gios.station_id
    )
    if old_entity_id is not None:
        entity_registry.async_update_entity(
            old_entity_id, new_unique_id=str(coordinator.gios.station_id)
        )

    async_add_entities([GiosAirQuality(coordinator, name)])


class GiosAirQuality(CoordinatorEntity, AirQualityEntity):
    """Define an GIOS sensor."""

    coordinator: GiosDataUpdateCoordinator

    def __init__(self, coordinator: GiosDataUpdateCoordinator, name: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._name = name
        self._attrs: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.air_quality_index is not None and self.air_quality_index in ICONS_MAP:
            return ICONS_MAP[self.air_quality_index]
        return "mdi:blur"

    @property
    def air_quality_index(self) -> str | None:
        """Return the air quality index."""
        return cast(Optional[str], self.coordinator.data.get(API_AQI, {}).get("value"))

    @property
    def particulate_matter_2_5(self) -> float | None:
        """Return the particulate matter 2.5 level."""
        return round_state(self._get_sensor_value(API_PM25))

    @property
    def particulate_matter_10(self) -> float | None:
        """Return the particulate matter 10 level."""
        return round_state(self._get_sensor_value(API_PM10))

    @property
    def ozone(self) -> float | None:
        """Return the O3 (ozone) level."""
        return round_state(self._get_sensor_value(API_O3))

    @property
    def carbon_monoxide(self) -> float | None:
        """Return the CO (carbon monoxide) level."""
        return round_state(self._get_sensor_value(API_CO))

    @property
    def sulphur_dioxide(self) -> float | None:
        """Return the SO2 (sulphur dioxide) level."""
        return round_state(self._get_sensor_value(API_SO2))

    @property
    def nitrogen_dioxide(self) -> float | None:
        """Return the NO2 (nitrogen dioxide) level."""
        return round_state(self._get_sensor_value(API_NO2))

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        return str(self.coordinator.gios.station_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, str(self.coordinator.gios.station_id))},
            "name": DEFAULT_NAME,
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        for sensor in SENSOR_MAP:
            if sensor in self.coordinator.data:
                self._attrs[f"{SENSOR_MAP[sensor]}_index"] = self.coordinator.data[
                    sensor
                ]["index"]
        self._attrs[ATTR_STATION] = self.coordinator.gios.station_name
        return self._attrs

    def _get_sensor_value(self, sensor: str) -> float | None:
        """Return value of specified sensor."""
        if sensor in self.coordinator.data:
            return cast(float, self.coordinator.data[sensor]["value"])
        return None


def round_state(state: float | None) -> float | None:
    """Round state."""
    return round(state) if state is not None else None
