"""Sensor for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from __future__ import annotations

import voluptuous as vol
from zamg import ZamgData

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_MILLIMETERS,
    PRESSURE_HPA,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_STATION_ID, DOMAIN, LOGGER, MANUFACTURER_URL
from .coordinator import ZamgDataUpdateCoordinator

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_STATION_ID): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZAMG weather platform."""

    probe = ZamgData(session=async_get_clientsession(hass))

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    station_id = config.get(CONF_STATION_ID)
    if station_id not in await probe.zamg_stations():
        LOGGER.warning(
            "Configured station_id %s could not be found at zamg, adding the nearest weather station instead",
            station_id,
        )
        station_id = await probe.closest_station(latitude, longitude)
    probe.set_default_station(station_id)

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.1.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    # No config entry exists and configuration.yaml config exists, trigger the import flow.
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_STATION_ID):
            return
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: station_id, CONF_NAME: config.get(CONF_NAME, "")},
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ZAMG weather platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [ZamgWeather(coordinator, entry.title, entry.data[CONF_STATION_ID])]
    )


class ZamgWeather(CoordinatorEntity, WeatherEntity):
    """Representation of a weather condition."""

    def __init__(
        self, coordinator: ZamgDataUpdateCoordinator, name, station_id
    ) -> None:
        """Initialise the platform with a data instance and station name."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{name}_{station_id}"
        self._attr_name = f"ZAMG {name}"
        self.station_id = f"{station_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, station_id)},
            manufacturer=ATTRIBUTION,
            configuration_url=MANUFACTURER_URL,
            name=coordinator.name,
        )
        # set units of ZAMG API
        self._attr_native_temperature_unit = TEMP_CELSIUS
        self._attr_native_pressure_unit = PRESSURE_HPA
        self._attr_native_wind_speed_unit = SPEED_METERS_PER_SECOND
        self._attr_native_precipitation_unit = LENGTH_MILLIMETERS

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return None

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        try:
            return float(self.coordinator.data[self.station_id].get("TL")["data"])
        except (TypeError, ValueError):
            return None

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        try:
            return float(self.coordinator.data[self.station_id].get("P")["data"])
        except (TypeError, ValueError):
            return None

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        try:
            return float(self.coordinator.data[self.station_id].get("RFAM")["data"])
        except (TypeError, ValueError):
            return None

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        try:
            return float(self.coordinator.data[self.station_id].get("FF")["data"])
        except (TypeError, ValueError):
            return None

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        try:
            return self.coordinator.data[self.station_id].get("DD")["data"]
        except (TypeError, ValueError):
            return None
