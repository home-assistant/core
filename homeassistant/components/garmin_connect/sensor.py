"""Platform for Garmin Connect integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_ID, DEVICE_CLASS_TIMESTAMP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .alarm_util import calculate_next_active_alarms
from .const import (
    ATTRIBUTION,
    DATA_COORDINATOR,
    DOMAIN as GARMIN_DOMAIN,
    GARMIN_ENTITY_LIST,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Garmin Connect sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[GARMIN_DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    unique_id = entry.data[CONF_ID]

    entities = []
    for (
        sensor_type,
        (name, unit, icon, device_class, enabled_by_default),
    ) in GARMIN_ENTITY_LIST.items():

        _LOGGER.debug(
            "Registering entity: %s, %s, %s, %s, %s, %s",
            sensor_type,
            name,
            unit,
            icon,
            device_class,
            enabled_by_default,
        )
        entities.append(
            GarminConnectSensor(
                coordinator,
                unique_id,
                sensor_type,
                name,
                unit,
                icon,
                device_class,
                enabled_by_default,
            )
        )

    async_add_entities(entities)


class GarminConnectSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Garmin Connect Sensor."""

    def __init__(
        self,
        coordinator,
        unique_id,
        sensor_type,
        name,
        unit,
        icon,
        device_class,
        enabled_default: bool = True,
    ):
        """Initialize a Garmin Connect sensor."""
        super().__init__(coordinator)

        self._unique_id = unique_id
        self._type = sensor_type
        self._name = name
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._enabled_default = enabled_default

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.coordinator.data or not self.coordinator.data[self._type]:
            return None

        value = self.coordinator.data[self._type]
        if "Duration" in self._type or "Seconds" in self._type:
            value = value // 60
        elif "Mass" in self._type or self._type == "weight":
            value = value / 1000
        elif self._type == "nextAlarm":
            active_alarms = calculate_next_active_alarms(
                self.coordinator.data[self._type]
            )
            if active_alarms:
                value = active_alarms[0]

        if self._device_class == DEVICE_CLASS_TIMESTAMP:
            return value

        return round(value, 2)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self._unique_id}_{self._type}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def extra_state_attributes(self):
        """Return attributes for sensor."""
        if not self.coordinator.data:
            return {}

        attributes = {
            "source": self.coordinator.data["source"],
            "last_synced": self.coordinator.data["lastSyncTimestampGMT"],
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        if self._type == "nextAlarm":
            attributes["next_alarms"] = calculate_next_active_alarms(
                self.coordinator.data[self._type]
            )

        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(GARMIN_DOMAIN, self._unique_id)},
            "name": "Garmin Connect",
            "manufacturer": "Garmin Connect",
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.data
            and self._type in self.coordinator.data
        )

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class
