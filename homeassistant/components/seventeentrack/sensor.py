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

    _attr_icon = ICON
    _attr_unit_of_measurement = "packages"

    def __init__(self, coordinator: SeventeenTrackDataCoordinator) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._name = coordinator.config_entry.data[CONF_NAME]
        self._username = coordinator.config_entry.data[CONF_USERNAME]
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this 17Track instance."""
        return {
            "identifiers": {(DOMAIN, self._username)},
            "name": self._username,
            "manufacturer": "17Track",
            "entry_type": "service",
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class SeventeenTrackPackagesSensor(SeventeenTrackBaseSensor):
    """Define sensor for all packages."""

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name} all packages"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return f"{self._username}-{slugify(self.name)}"

    @property
    def state(self) -> int:
        """Return the state."""
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
        self.sensor_type = sensor_type

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name} packages {self.sensor_type}"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return f"{self._username}-{slugify(self.name)}"

    @property
    def state(self) -> str:
        """Return the state."""
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
