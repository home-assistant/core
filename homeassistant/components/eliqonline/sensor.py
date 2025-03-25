"""Monitors home energy use for the ELIQ Online service."""

from __future__ import annotations

from datetime import timedelta
import logging

import eliqonline
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_CHANNEL_ID = "channel_id"

DEFAULT_NAME = "ELIQ Online"

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_CHANNEL_ID): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ELIQ Online sensor."""
    access_token = config.get(CONF_ACCESS_TOKEN)
    name = config.get(CONF_NAME, DEFAULT_NAME)
    channel_id = config.get(CONF_CHANNEL_ID)
    session = async_get_clientsession(hass)

    api = eliqonline.API(session=session, access_token=access_token)

    try:
        _LOGGER.debug("Probing for access to ELIQ Online API")
        await api.get_data_now(channelid=channel_id)
    except OSError as error:
        _LOGGER.error("Could not access the ELIQ Online API: %s", error)
        return

    async_add_entities([EliqSensor(api, channel_id, name)], True)


class EliqSensor(SensorEntity):
    """Implementation of an ELIQ Online sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, api, channel_id, name):
        """Initialize the sensor."""
        self._attr_name = name
        self._api = api
        self._channel_id = channel_id

    async def async_update(self) -> None:
        """Get the latest data."""
        try:
            response = await self._api.get_data_now(channelid=self._channel_id)
            self._attr_native_value = int(response["power"])
            _LOGGER.debug("Updated power from server %d W", self.native_value)
        except KeyError:
            _LOGGER.warning("Invalid response from ELIQ Online API")
        except (OSError, TimeoutError) as error:
            _LOGGER.warning("Could not connect to the ELIQ Online API: %s", error)
