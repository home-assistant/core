"""Support for the ZCS Azzurro platform."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import dateutil.parser

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import realtime_data_request
from .const import (
    REALTIME_BATTERY_CYCLES_KEY,
    REALTIME_BATTERY_SOC_KEY,
    REALTIME_ENERGY_AUTOCONSUMING_TOTAL_KEY,
    REALTIME_ENERGY_CHARGING_KEY,
    REALTIME_ENERGY_CHARGING_TOTAL_KEY,
    REALTIME_ENERGY_CONSUMING_KEY,
    REALTIME_ENERGY_CONSUMING_TOTAL_KEY,
    REALTIME_ENERGY_DISCHARGING_KEY,
    REALTIME_ENERGY_DISCHARGING_TOTAL_KEY,
    REALTIME_ENERGY_EXPORTING_KEY,
    REALTIME_ENERGY_EXPORTING_TOTAL_KEY,
    REALTIME_ENERGY_GENERATING_KEY,
    REALTIME_ENERGY_GENERATING_TOTAL_KEY,
    REALTIME_ENERGY_IMPORTING_KEY,
    REALTIME_ENERGY_IMPORTING_TOTAL_KEY,
    REALTIME_LAST_COMM_KEY,
    REALTIME_LAST_UPDATE_KEY,
    REALTIME_POWER_AUTOCONSUMING_KEY,
    REALTIME_POWER_CHARGING_KEY,
    REALTIME_POWER_CONSUMING_KEY,
    REALTIME_POWER_DISCHARGING_KEY,
    REALTIME_POWER_EXPORTING_KEY,
    REALTIME_POWER_GENERATING_KEY,
    REALTIME_POWER_IMPORTING_KEY,
    SCHEMA_CLIENT_KEY,
    SCHEMA_THINGS_KEY,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ZcsAzzurroSensorEntityDescription(SensorEntityDescription):
    """Describes Tuya sensor entity."""


SENSOR_TYPES = (
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_BATTERY_CYCLES_KEY,
        name="Battery cycles",
        icon="mdi:solar-power-variant",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_BATTERY_SOC_KEY,
        name="Battery SoC",
        icon="mdi:home-battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_AUTOCONSUMING_TOTAL_KEY,
        name="Total autoconsumed energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_CHARGING_KEY,
        name="Charged energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_CHARGING_TOTAL_KEY,
        name="Total charged energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_CONSUMING_KEY,
        name="Consumed energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_CONSUMING_TOTAL_KEY,
        name="Total consumed energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_DISCHARGING_KEY,
        name="Discharged energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_DISCHARGING_TOTAL_KEY,
        name="Total discharged energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_EXPORTING_KEY,
        name="Exported energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_EXPORTING_TOTAL_KEY,
        name="Total exported energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_GENERATING_KEY,
        name="Generated energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_GENERATING_TOTAL_KEY,
        name="Total generated energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_IMPORTING_KEY,
        name="Imported energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_ENERGY_IMPORTING_TOTAL_KEY,
        name="Total imported energy",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_LAST_COMM_KEY,
        name="Rename me",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_LAST_UPDATE_KEY,
        name="Rename me",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_POWER_AUTOCONSUMING_KEY,
        name="Autoconsuming power",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_POWER_CHARGING_KEY,
        name="Charging power",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_POWER_CONSUMING_KEY,
        name="Consuming power",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_POWER_DISCHARGING_KEY,
        name="Discharging power",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_POWER_EXPORTING_KEY,
        name="Exporting power",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_POWER_GENERATING_KEY,
        name="Generating power",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
    ),
    ZcsAzzurroSensorEntityDescription(
        key=REALTIME_POWER_IMPORTING_KEY,
        name="Importing power",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Azzurro sensor."""
    _LOGGER.debug("Received data during setup is %s", entry.data)
    data = entry.data
    realtime_sensors_available = await realtime_data_request(
        hass,
        data[SCHEMA_CLIENT_KEY],
        data[SCHEMA_THINGS_KEY],
    )
    available_realtime_keys = list(realtime_sensors_available.keys())
    _LOGGER.debug("available realtime keys are %s", ", ".join(available_realtime_keys))
    async_add_entities(
        ZcsAzzurroSensor(
            hass=hass,
            description=description,
            client=data[SCHEMA_CLIENT_KEY],
            thing=data[SCHEMA_THINGS_KEY],
            available_realtime_keys=available_realtime_keys,
        )
        for description in SENSOR_TYPES
        if description.key in available_realtime_keys
    )


class ZcsAzzurroSensor(SensorEntity):
    """Implementation of the ZcsAzzurro sensor."""

    entity_description: ZcsAzzurroSensorEntityDescription

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        description: ZcsAzzurroSensorEntityDescription,
        client: str,
        thing: str,
        available_realtime_keys: list,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.entity_description = description
        self.hass = hass
        self.client = client
        self.thing = thing
        self._attr_unique_id = f"{self.client}_{self.thing}_{description.key}"
        self.entity_description.name = f"{self.thing} {self.entity_description.name}"
        self.fetched_data: dict[str, Any] = {}
        self.available_realtime_keys = available_realtime_keys
        _LOGGER.debug("element initialized")

    @property
    def native_value(self) -> int | float | datetime | None:
        """Return sensor state."""
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            try:
                str_val: str = self.fetched_data.get(self.entity_description.key, "")
                _LOGGER.debug(
                    "native value of datetime is %s",
                    str_val,
                )
                return dateutil.parser.isoparse(str_val)
            except TypeError:
                return None
        elif self.entity_description.state_class == SensorStateClass.TOTAL_INCREASING:
            try:
                return abs(self.fetched_data.get(self.entity_description.key, None))
            except TypeError:
                return None
        return self.fetched_data.get(self.entity_description.key, None)

    async def async_update(self) -> None:
        """Update sensor values."""
        self.fetched_data = await realtime_data_request(
            self.hass,
            self.client,
            self.thing,
            self.available_realtime_keys,
        )
        _LOGGER.debug("fetched data %s", self.fetched_data)
