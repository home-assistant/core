"""Support for ComEd Hourly Pricing data."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, CONF_OFFSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)
_RESOURCE = "https://hourlypricing.comed.com/api"

SCAN_INTERVAL = timedelta(minutes=5)

ATTRIBUTION = "Data provided by ComEd Hourly Pricing service"

CONF_CURRENT_HOUR_AVERAGE = "current_hour_average"
CONF_FIVE_MINUTE = "five_minute"
CONF_MONITORED_FEEDS = "monitored_feeds"
CONF_SENSOR_TYPE = "type"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CONF_FIVE_MINUTE,
        name="ComEd 5 Minute Price",
        native_unit_of_measurement="c",
    ),
    SensorEntityDescription(
        key=CONF_CURRENT_HOUR_AVERAGE,
        name="ComEd Current Hour Average Price",
        native_unit_of_measurement="c",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

TYPES_SCHEMA = vol.In(SENSOR_KEYS)

SENSORS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSOR_TYPE): TYPES_SCHEMA,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_OFFSET, default=0.0): vol.Coerce(float),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_MONITORED_FEEDS): [SENSORS_SCHEMA]}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ComEd Hourly Pricing sensor."""
    websession = async_get_clientsession(hass)

    entities = [
        ComedHourlyPricingSensor(
            websession,
            variable[CONF_OFFSET],
            variable.get(CONF_NAME),
            description,
        )
        for variable in config[CONF_MONITORED_FEEDS]
        for description in SENSOR_TYPES
        if description.key == variable[CONF_SENSOR_TYPE]
    ]

    async_add_entities(entities, True)


class ComedHourlyPricingSensor(SensorEntity):
    """Implementation of a ComEd Hourly Pricing sensor."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(self, websession, offset, name, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.websession = websession
        if name:
            self._attr_name = name
        self.offset = offset

    async def async_update(self) -> None:
        """Get the ComEd Hourly Pricing data from the web service."""
        try:
            sensor_type = self.entity_description.key
            if sensor_type in (CONF_FIVE_MINUTE, CONF_CURRENT_HOUR_AVERAGE):
                url_string = _RESOURCE
                if sensor_type == CONF_FIVE_MINUTE:
                    url_string += "?type=5minutefeed"
                else:
                    url_string += "?type=currenthouraverage"

                async with async_timeout.timeout(60):
                    response = await self.websession.get(url_string)
                    # The API responds with MIME type 'text/html'
                    text = await response.text()
                    data = json.loads(text)
                    self._attr_native_value = round(
                        float(data[0]["price"]) + self.offset, 2
                    )

            else:
                self._attr_native_value = None

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Could not get data from ComEd API: %s", err)
        except (ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
