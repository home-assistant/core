"""Sensor for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from __future__ import annotations

import voluptuous as vol
from zamg import ZamgData

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    DEGREE,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    LOGGER.warning(
        "Configuration of the zamg integration in YAML is deprecated and "
        "will be removed in a further release of Home Assistant; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )

    probe = ZamgData()

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    station_id = config.get(CONF_STATION_ID) or probe.closest_station(
        latitude, longitude, hass.config.config_dir
    )
    probe.set_default_station(station_id)

    async_add_entities(
        [ZamgWeather(probe, probe.get_data("Name", station_id), station_id)]
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

    @property
    def condition(self):
        """Return the current condition."""
        return None

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def native_temperature(self):
        """Return the platform temperature."""
        return float(
            str(
                self.coordinator.data[self.station_id].get(f"T {TEMP_CELSIUS}")
            ).replace(",", ".")
        )

    @property
    def native_pressure(self):
        """Return the pressure."""
        return float(
            str(self.coordinator.data[self.station_id].get("LDstat hPa")).replace(
                ",", "."
            )
        )

    @property
    def humidity(self):
        """Return the humidity."""
        return float(
            str(self.coordinator.data[self.station_id].get("RF %")).replace(",", ".")
        )

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        return float(
            str(
                self.coordinator.data[self.station_id].get(
                    f"WG {SPEED_KILOMETERS_PER_HOUR}"
                )
            ).replace(",", ".")
        )

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.coordinator.data[self.station_id].get(f"WR {DEGREE}")
