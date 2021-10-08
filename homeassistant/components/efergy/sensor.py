"""Support for Efergy sensors."""
from __future__ import annotations

from pyefergy import Efergy
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_APPTOKEN = "app_token"
CONF_UTC_OFFSET = "utc_offset"

CONF_PERIOD = "period"

CONF_INSTANT = "instant_readings"
CONF_AMOUNT = "amount"
CONF_BUDGET = "budget"
CONF_COST = "cost"
CONF_CURRENT_VALUES = "current_values"

DEFAULT_PERIOD = "year"
DEFAULT_UTC_OFFSET = "0"

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    CONF_INSTANT: SensorEntityDescription(
        key=CONF_INSTANT,
        name="Energy Usage",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
    ),
    CONF_AMOUNT: SensorEntityDescription(
        key=CONF_AMOUNT,
        name="Energy Consumed",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    CONF_BUDGET: SensorEntityDescription(
        key=CONF_BUDGET,
        name="Energy Budget",
    ),
    CONF_COST: SensorEntityDescription(
        key=CONF_COST,
        name="Energy Cost",
        device_class=DEVICE_CLASS_MONETARY,
    ),
    CONF_CURRENT_VALUES: SensorEntityDescription(
        key=CONF_CURRENT_VALUES,
        name="Per-Device Usage",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
    ),
}

TYPES_SCHEMA = vol.In(SENSOR_TYPES)

SENSORS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): TYPES_SCHEMA,
        vol.Optional(CONF_CURRENCY, default=""): cv.string,
        vol.Optional(CONF_PERIOD, default=DEFAULT_PERIOD): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APPTOKEN): cv.string,
        vol.Optional(CONF_UTC_OFFSET, default=DEFAULT_UTC_OFFSET): cv.string,
        vol.Required(CONF_MONITORED_VARIABLES): [SENSORS_SCHEMA],
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the Efergy sensor."""
    api = Efergy(
        config[CONF_APPTOKEN],
        async_get_clientsession(hass),
        utc_offset=config[CONF_UTC_OFFSET],
    )

    dev = []
    sensors = await api.get_sids()
    for variable in config[CONF_MONITORED_VARIABLES]:
        if variable[CONF_TYPE] == CONF_CURRENT_VALUES:
            for sensor in sensors:
                dev.append(
                    EfergySensor(
                        api,
                        variable[CONF_PERIOD],
                        variable[CONF_CURRENCY],
                        SENSOR_TYPES[variable[CONF_TYPE]],
                        sid=sensor["sid"],
                    )
                )
        dev.append(
            EfergySensor(
                api,
                variable[CONF_PERIOD],
                variable[CONF_CURRENCY],
                SENSOR_TYPES[variable[CONF_TYPE]],
            )
        )

    add_entities(dev, True)


class EfergySensor(SensorEntity):
    """Implementation of an Efergy sensor."""

    def __init__(
        self,
        api: Efergy,
        period: str,
        currency: str,
        description: SensorEntityDescription,
        sid: str = None,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.sid = sid
        self.api = api
        self.period = period
        if sid:
            self._attr_name = f"efergy_{sid}"
        if description.key == CONF_COST:
            self._attr_native_unit_of_measurement = f"{currency}/{period}"

    async def async_update(self) -> None:
        """Get the Efergy monitor data from the web service."""
        self._attr_native_value = await self.api.async_get_reading(
            self.entity_description.key, period=self.period, sid=self.sid
        )
