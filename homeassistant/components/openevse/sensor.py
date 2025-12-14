"""Support for monitoring an OpenEVSE Charger."""

from __future__ import annotations

from datetime import timedelta
import logging

from requests import RequestException

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ConfigEntry

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status",
        name="Charging Status",
    ),
    SensorEntityDescription(
        key="charge_time",
        name="Charge Time Elapsed",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ambient_temp",
        name="Ambient Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ir_temp",
        name="IR Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rtc_temp",
        name="RTC Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="usage_session",
        name="Usage this Session",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="usage_total",
        name="Total Usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="charging_current",
        name="Current charging current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    async_add_entities(
        [
            OpenEVSESensor(config_entry.data[CONF_HOST], config_entry, description)
            for description in SENSOR_TYPES
        ]
    )


class OpenEVSESensor(SensorEntity):
    """Implementation of an OpenEVSE sensor."""

    def __init__(
        self, host: str, entry: ConfigEntry, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.unique_id = f"{host}: {description.key}"
        self.entity_description = description
        self.host = host
        self.entry = entry

    def update(self) -> None:
        """Get the monitored data from the charger."""
        try:
            sensor_type = self.entity_description.key
            if sensor_type == "status":
                self._attr_native_value = self.entry.runtime_data.getStatus()
            elif sensor_type == "charge_time":
                self._attr_native_value = (
                    self.entry.runtime_data.getChargeTimeElapsed() / 60
                )
            elif sensor_type == "ambient_temp":
                self._attr_native_value = (
                    self.entry.runtime_data.getAmbientTemperature()
                )
            elif sensor_type == "ir_temp":
                self._attr_native_value = self.entry.runtime_data.getIRTemperature()
            elif sensor_type == "rtc_temp":
                self._attr_native_value = self.entry.runtime_data.getRTCTemperature()
            elif sensor_type == "usage_session":
                self._attr_native_value = (
                    float(self.entry.runtime_data.getUsageSession()) / 1000
                )
            elif sensor_type == "usage_total":
                self._attr_native_value = (
                    float(self.entry.runtime_data.getUsageTotal()) / 1000
                )
            elif sensor_type == "charging_current":
                self._attr_native_value = self.entry.runtime_data.charging_current
            else:
                self._attr_native_value = "Unknown"
        except (RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added."""
        if self.entity_description.key in ["ir_temp", "rtc_temp"]:
            return False
        return True

    @property
    def device_info(self):
        """Return device information for the OpenEVSE charger."""
        return {
            "identifiers": {("openevse", self.host)},
            "name": f"OpenEVSE {self.host}",
            "manufacturer": "OpenEVSE",
        }
