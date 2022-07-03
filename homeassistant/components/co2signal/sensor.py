"""Support for the CO2signal platform."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import cast

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CO2SignalCoordinator
from .const import ATTRIBUTION, DOMAIN

SCAN_INTERVAL = timedelta(minutes=3)


@dataclass
class CO2SensorEntityDescription:
    """Provide a description of a CO2 sensor."""

    key: str
    name: str
    unit_of_measurement: str | None = None
    # For backwards compat, allow description to override unique ID key to use
    unique_id: str | None = None


SENSORS = (
    CO2SensorEntityDescription(
        key="carbonIntensity",
        name="CO2 intensity",
        unique_id="co2intensity",
        # No unit, it's extracted from response.
    ),
    CO2SensorEntityDescription(
        key="fossilFuelPercentage",
        name="Grid fossil fuel percentage",
        unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the CO2signal sensor."""
    coordinator: CO2SignalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(CO2Sensor(coordinator, description) for description in SENSORS)


class CO2Sensor(CoordinatorEntity[CO2SignalCoordinator], SensorEntity):
    """Implementation of the CO2Signal sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:molecule-co2"

    def __init__(
        self, coordinator: CO2SignalCoordinator, description: CO2SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._description = description

        name = description.name
        if extra_name := coordinator.get_extra_name():
            name = f"{extra_name} - {name}"

        self._attr_name = name
        self._attr_extra_state_attributes = {
            "country_code": coordinator.data["countryCode"],
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.electricitymap.org/",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.entry_id)},
            manufacturer="Tmrow.com",
            name="CO2 signal",
        )
        self._attr_unique_id = (
            f"{coordinator.entry_id}_{description.unique_id or description.key}"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self._description.key in self.coordinator.data["data"]
        )

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        if (value := self.coordinator.data["data"][self._description.key]) is None:  # type: ignore[literal-required]
            return None
        return round(value, 2)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self._description.unit_of_measurement:
            return self._description.unit_of_measurement
        return cast(str, self.coordinator.data["units"].get(self._description.key))
