"""Support for Efergy sensors."""
from __future__ import annotations

from re import sub
from typing import cast

from pyefergy import Efergy
from pyefergy.exceptions import ConnectError, DataError, ServiceError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import StateType

from . import EfergyEntity
from .const import CONF_CURRENT_VALUES, DOMAIN, LOGGER

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="instant_readings",
        name="Power Usage",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy_day",
        name="Daily Consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_week",
        name="Weekly Consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_month",
        name="Monthly Consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_year",
        name="Yearly Consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="budget",
        name="Energy Budget",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cost_day",
        name="Daily Energy Cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cost_week",
        name="Weekly Energy Cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cost_month",
        name="Monthly Energy Cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="cost_year",
        name="Yearly Energy Cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=CONF_CURRENT_VALUES,
        name="Power Usage",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Efergy sensors."""
    api: Efergy = hass.data[DOMAIN][entry.entry_id]
    sensors = []
    for description in SENSOR_TYPES:
        if description.key != CONF_CURRENT_VALUES:
            sensors.append(
                EfergySensor(
                    api,
                    description,
                    entry.entry_id,
                    period=sub("^energy_|^cost_", "", description.key),
                    currency=hass.config.currency,
                )
            )
        else:
            description.entity_registry_enabled_default = len(api.sids) > 1
            for sid in api.sids:
                sensors.append(
                    EfergySensor(
                        api,
                        description,
                        entry.entry_id,
                        sid=sid,
                    )
                )
    async_add_entities(sensors, True)


class EfergySensor(EfergyEntity, SensorEntity):
    """Implementation of an Efergy sensor."""

    def __init__(
        self,
        api: Efergy,
        description: SensorEntityDescription,
        server_unique_id: str,
        period: str | None = None,
        currency: str | None = None,
        sid: int | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(api, server_unique_id)
        self.entity_description = description
        if description.key == CONF_CURRENT_VALUES:
            self._attr_name = f"{description.name}_{'' if sid is None else sid}"
        self._attr_unique_id = (
            f"{server_unique_id}/{description.key}_{'' if sid is None else sid}"
        )
        if "cost" in description.key:
            self._attr_native_unit_of_measurement = currency
        self.sid = sid
        self.period = period

    async def async_update(self) -> None:
        """Get the Efergy monitor data from the web service."""
        try:
            data = await self.api.async_get_reading(
                self.entity_description.key, period=self.period, sid=self.sid
            )
            self._attr_native_value = cast(StateType, data)
        except (ConnectError, DataError, ServiceError) as ex:
            if self._attr_available:
                self._attr_available = False
                LOGGER.error("Error getting data: %s", ex)
            return
        if not self._attr_available:
            self._attr_available = True
            LOGGER.info("Connection has resumed")
