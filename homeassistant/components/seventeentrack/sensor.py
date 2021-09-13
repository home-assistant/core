"""Support for package tracking sensors from 17track.net."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.seventeentrack import SeventeenTrackDataCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_FRIENDLY_NAME,
    ATTR_LOCATION,
    CONF_NAME,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    ATTR_DESTINATION_COUNTRY,
    ATTR_INFO_TEXT,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_TYPE,
    ATTR_PACKAGES,
    ATTR_STATUS,
    ATTR_TIMESTAMP,
    ATTR_TRACKING_INFO_LANGUAGE,
    ATTRIBUTION,
    DOMAIN,
    ICON,
)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the SeventeenTrack sensors."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SeventeenTrackBaseSensor] = []
    for sensor_type in coordinator.data["summary"]:
        entities.append(SeventeenTrackSummarySensor(coordinator, sensor_type))
    entities.append(SeventeenTrackPackagesSensor(coordinator))

    async_add_entities(entities)


class SeventeenTrackBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for SeventeenTrack sensors."""

    coordinator: SeventeenTrackDataCoordinator
    _attr_icon = ICON
    _attr_native_unit_of_measurement = "packages"

    def __init__(self, coordinator: SeventeenTrackDataCoordinator) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_name: str = coordinator.config_entry.data[CONF_NAME]
        self._username: str = coordinator.config_entry.data[CONF_USERNAME]
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this 17Track instance."""
        return {
            "identifiers": {(DOMAIN, self._username)},
            "default_name": self.coordinator.config_entry.data[CONF_NAME],
            "manufacturer": "17Track",
            "entry_type": "service",
        }


class SeventeenTrackPackagesSensor(SeventeenTrackBaseSensor):
    """Define sensor for all packages."""

    def __init__(self, coordinator: SeventeenTrackDataCoordinator) -> None:
        """Initialize package sensor."""
        super().__init__(coordinator)
        self._attr_name = f"{self._attr_name} all packages"
        self._attr_unique_id = f"{self._username}-{slugify(self._attr_name)}"

    @property
    def native_value(self) -> int:
        """Return the native value."""
        return len(self.coordinator.data["packages"])

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        package_data = {}
        for package in self.coordinator.data["packages"]:
            package_data.update(
                {
                    package.tracking_number: {
                        ATTR_FRIENDLY_NAME: package.friendly_name,
                        ATTR_INFO_TEXT: package.info_text,
                        ATTR_TIMESTAMP: package.timestamp,
                        ATTR_STATUS: package.status,
                        ATTR_LOCATION: package.location,
                        ATTR_TRACKING_INFO_LANGUAGE: package.tracking_info_language,
                        ATTR_PACKAGE_TYPE: package.package_type,
                        ATTR_ORIGIN_COUNTRY: package.origin_country,
                        ATTR_DESTINATION_COUNTRY: package.destination_country,
                    }
                }
            )

        if package_data:
            self._attrs[ATTR_PACKAGES] = package_data

        return self._attrs


class SeventeenTrackSummarySensor(SeventeenTrackBaseSensor):
    """Define packages summary sensor."""

    def __init__(
        self, coordinator: SeventeenTrackDataCoordinator, sensor_type: str
    ) -> None:
        """Initialize the sensor type."""
        super().__init__(coordinator)
        self._attr_name = f"{self._attr_name} packages {sensor_type}"
        self._attr_unique_id = f"{self._username}-{slugify(self._attr_name)}"
        self.sensor_type = sensor_type

    @property
    def native_value(self) -> str:
        """Return the native value."""
        return self.coordinator.data["summary"][self.sensor_type]

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        package_data = {}
        for package in self.coordinator.data["packages"]:
            if package.status == self.sensor_type:
                package_data.update(
                    {
                        package.tracking_number: {
                            ATTR_FRIENDLY_NAME: package.friendly_name,
                            ATTR_INFO_TEXT: package.info_text,
                            ATTR_TIMESTAMP: package.timestamp,
                            ATTR_STATUS: package.status,
                            ATTR_LOCATION: package.location,
                            ATTR_TRACKING_INFO_LANGUAGE: package.tracking_info_language,
                            ATTR_PACKAGE_TYPE: package.package_type,
                            ATTR_ORIGIN_COUNTRY: package.origin_country,
                            ATTR_DESTINATION_COUNTRY: package.destination_country,
                        }
                    }
                )

        if package_data:
            self._attrs[ATTR_PACKAGES] = package_data

        return self._attrs
