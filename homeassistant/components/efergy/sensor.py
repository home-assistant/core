"""Support for Efergy sensors."""

from __future__ import annotations

import dataclasses
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
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import EfergyEntity
from .const import CONF_CURRENT_VALUES, DOMAIN, LOGGER

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="instant_readings",
        translation_key="instant_readings",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy_day",
        translation_key="energy_day",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_week",
        translation_key="energy_week",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_month",
        translation_key="energy_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_year",
        translation_key="energy_year",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="budget",
        translation_key="budget",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cost_day",
        translation_key="cost_day",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cost_week",
        translation_key="cost_week",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cost_month",
        translation_key="cost_month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="cost_year",
        translation_key="cost_year",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=CONF_CURRENT_VALUES,
        translation_key="power_usage",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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
            description = dataclasses.replace(
                description,
                entity_registry_enabled_default=len(api.sids) > 1,
            )
            sensors.extend(
                EfergySensor(
                    api,
                    description,
                    entry.entry_id,
                    sid=sid,
                )
                for sid in api.sids
            )
    async_add_entities(sensors, True)


class EfergySensor(EfergyEntity, SensorEntity):
    """Implementation of an Efergy sensor."""

    _attr_has_entity_name = True

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
            assert sid is not None
            self._attr_translation_placeholders = {"sid": str(sid)}
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
