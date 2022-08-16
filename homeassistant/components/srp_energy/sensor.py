"""Support for SRP Energy Sensor."""
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    AGGRAGATE_ENTITY_KEYS,
    ATTRIBUTION,
    DATA_SUMMARY_KEY_DATETIME,
    DATA_SUMMARY_KEY_DAY,
    DATA_SUMMARY_KEY_HOUR,
    DATA_SUMMARY_KEY_VALUE,
    DEFAULT_NAME,
    DEVICE_CONFIG_URL,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
    FRIENDLY_DAY_FORMAT,
    FRIENDLY_HOUR_FORMAT,
    SENSOR_ENTITIES,
)
from .coordinator import SrpAggregateData, SrpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SRP Energy Usage sensor."""
    _LOGGER.debug("Setup Sensor Entities")
    entry_unique_id: str = getattr(entry, "unique_id", DEFAULT_NAME)
    coordinator: SrpCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[SrpEnergySensorBaseEntity] = []
    for entity_description, device_name in SENSOR_ENTITIES:

        if entity_description.key in AGGRAGATE_ENTITY_KEYS:
            sensors.append(
                SrpEnergyAggregateSensorEntity(
                    entity_description=entity_description,
                    coordinator=coordinator,
                    entry_unique_id=entry_unique_id,
                    device_name=device_name,
                )
            )
        else:
            sensors.append(
                SrpEnergySensorEntity(
                    entity_description=entity_description,
                    coordinator=coordinator,
                    entry_unique_id=entry_unique_id,
                    device_name=device_name,
                )
            )

    async_add_entities(sensors)


class SrpEnergySensorBaseEntity(CoordinatorEntity[SrpCoordinator], SensorEntity):
    """Abstract class for an srp_energy sensor."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    entity_description: SensorEntityDescription

    def __init__(
        self,
        entity_description: SensorEntityDescription,
        coordinator: SrpCoordinator,
        entry_unique_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attrs: dict[str, Any] = {}
        unique_id: str = f"{entry_unique_id}_{entity_description.key}".lower()

        _LOGGER.debug("Setting entity name %s", unique_id)
        self._attr_unique_id = unique_id
        self._set_native_value()

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{self.coordinator.name}_{device_name}")},
            configuration_url=DEVICE_CONFIG_URL,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            name=f"{self.coordinator.name} {device_name}",
        )

    def _set_native_value(self) -> None:
        """Set the native value.

        To be extended by sub class.
        """


class SrpEnergySensorEntity(SrpEnergySensorBaseEntity):
    """Abstract class for an srp_energy sensor."""

    def _set_native_value(self) -> None:
        """Set native value for class."""
        self._attr_native_value = self.coordinator.data[self.entity_description.key]

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        _LOGGER.debug(
            "Reading entity native_value %s at %s",
            self.coordinator.data[self.entity_description.key],
            dt_util.now(),
        )
        return self.coordinator.data[self.entity_description.key]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        self._attrs["on_peak"] = 0.0
        self._attrs["off_peak"] = 0.0
        self._attrs["shoulder"] = 0.0
        self._attrs["super_off_peak"] = 0.0
        return self._attrs


class SrpEnergyAggregateSensorEntity(SrpEnergySensorBaseEntity):
    """Abstract class for an srp_energy aggregate sensor."""

    def __init__(
        self,
        entity_description: SensorEntityDescription,
        coordinator: SrpCoordinator,
        entry_unique_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        # Set details first because super().__init__ calls self._set_native_value()
        self._details: dict[str, SrpAggregateData] = (
            coordinator.data[entity_description.key]
            if coordinator.data[entity_description.key]
            else {}
        )

        super().__init__(entity_description, coordinator, entry_unique_id, device_name)

    def _set_native_value(self) -> None:
        """Set value from aggregate."""
        self._attr_native_value: float = self.summary_value()

    def summary_value(self) -> float:
        """Return summary value of the sensor."""
        total_value = 0.0
        for key in self._details.keys():
            total_value += float(self._details[key]["value"])
        return round(total_value, 2)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        self._details = (
            self.coordinator.data[self.entity_description.key]
            if self.coordinator.data[self.entity_description.key]
            else {}
        )
        summary_value: float = self.summary_value()

        _LOGGER.debug(
            "Reading entity native_value %s at %s",
            summary_value,
            dt_util.now(),
        )
        return summary_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        details = []

        # Remap details
        for key, value in sorted(self._details.items()):
            cur_datetime = dt_util.parse_datetime(key)

            if cur_datetime:
                prior = {
                    DATA_SUMMARY_KEY_DATETIME: key,
                    DATA_SUMMARY_KEY_DAY: cur_datetime.strftime(FRIENDLY_DAY_FORMAT),
                    DATA_SUMMARY_KEY_HOUR: cur_datetime.strftime(FRIENDLY_HOUR_FORMAT),
                    DATA_SUMMARY_KEY_VALUE: value[DATA_SUMMARY_KEY_VALUE],
                }
                details.append(prior)

        self._attrs["details"] = details
        return self._attrs
