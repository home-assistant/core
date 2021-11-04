"""Support for Efergy sensors."""
from __future__ import annotations

import logging
from re import sub

from pyefergy import Efergy, exceptions
import voluptuous as vol

from homeassistant.components.efergy import EfergyEntity
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_CURRENCY,
    CONF_MONITORED_VARIABLES,
    CONF_TYPE,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_APPTOKEN, CONF_CURRENT_VALUES, DATA_KEY_API, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="instant_readings",
        name="Power Usage",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy_day",
        name="Daily Consumption",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_week",
        name="Weekly Consumption",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_month",
        name="Monthly Consumption",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_year",
        name="Yearly Consumption",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
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
        device_class=DEVICE_CLASS_MONETARY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cost_week",
        name="Weekly Energy Cost",
        device_class=DEVICE_CLASS_MONETARY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cost_month",
        name="Monthly Energy Cost",
        device_class=DEVICE_CLASS_MONETARY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="cost_year",
        name="Yearly Energy Cost",
        device_class=DEVICE_CLASS_MONETARY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=CONF_CURRENT_VALUES,
        name="Power Usage",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)

TYPES_SCHEMA = vol.In(
    ["current_values", "instant_readings", "amount", "budget", "cost"]
)


SENSORS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): TYPES_SCHEMA,
        vol.Optional(CONF_CURRENCY, default=""): cv.string,
        vol.Optional("period", default="year"): cv.string,
    }
)

# Deprecated in Home Assistant 2021.11
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APPTOKEN): cv.string,
        vol.Optional("utc_offset", default="0"): cv.string,
        vol.Required(CONF_MONITORED_VARIABLES): [SENSORS_SCHEMA],
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Efergy sensor from yaml."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Efergy sensors."""
    api: Efergy = hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]
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
            description.entity_registry_enabled_default = len(api.info["sids"]) > 1
            for sid in api.info["sids"]:
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
        sid: str = "",
    ) -> None:
        """Initialize the sensor."""
        super().__init__(api, server_unique_id)
        self.entity_description = description
        if description.key == CONF_CURRENT_VALUES:
            self._attr_name = f"{description.name}_{sid}"
        self._attr_unique_id = f"{server_unique_id}/{description.key}_{sid}"
        if "cost" in description.key:
            self._attr_native_unit_of_measurement = currency
        self.sid = sid
        self.period = period

    async def async_update(self) -> None:
        """Get the Efergy monitor data from the web service."""
        try:
            self._attr_native_value = await self.api.async_get_reading(
                self.entity_description.key, period=self.period, sid=self.sid
            )
        except (exceptions.DataError, exceptions.ConnectError) as ex:
            if self._attr_available:
                self._attr_available = False
                _LOGGER.error("Error getting data: %s", ex)
            return
        if not self._attr_available:
            self._attr_available = True
            _LOGGER.info("Connection has resumed")
