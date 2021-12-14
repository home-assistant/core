"""Support for the CO2signal platform."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_TOKEN,
    PERCENTAGE,
)
from homeassistant.helpers import config_validation as cv, update_coordinator
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType

from . import CO2SignalCoordinator, CO2SignalResponse
from .const import ATTRIBUTION, CONF_COUNTRY_CODE, DOMAIN, MSG_LOCATION

SCAN_INTERVAL = timedelta(minutes=3)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coords", msg=MSG_LOCATION): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coords", msg=MSG_LOCATION): cv.longitude,
        vol.Optional(CONF_COUNTRY_CODE): cv.string,
    }
)


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


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CO2signal sensor."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=config,
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the CO2signal sensor."""
    coordinator: CO2SignalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(CO2Sensor(coordinator, description) for description in SENSORS)


class CO2Sensor(update_coordinator.CoordinatorEntity[CO2SignalResponse], SensorEntity):
    """Implementation of the CO2Signal sensor."""

    _attr_state_class = STATE_CLASS_MEASUREMENT
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
            super().available
            and self.coordinator.data["data"].get(self._description.key) is not None
        )

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return round(self.coordinator.data["data"][self._description.key], 2)  # type: ignore[misc]

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self._description.unit_of_measurement:
            return self._description.unit_of_measurement
        return cast(str, self.coordinator.data["units"].get(self._description.key))
