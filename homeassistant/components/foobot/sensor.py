"""Support for the Foobot indoor air quality monitor."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp
from foobot_async import FoobotClient
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_TOKEN,
    CONF_USERNAME,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_HUMIDITY = "humidity"
ATTR_PM2_5 = "PM2.5"
ATTR_CARBON_DIOXIDE = "CO2"
ATTR_VOLATILE_ORGANIC_COMPOUNDS = "VOC"
ATTR_FOOBOT_INDEX = "index"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="pm",
        name=ATTR_PM2_5,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:cloud",
    ),
    SensorEntityDescription(
        key="tmp",
        name=ATTR_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="hum",
        name=ATTR_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="co2",
        name=ATTR_CARBON_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:molecule-co2",
    ),
    SensorEntityDescription(
        key="voc",
        name=ATTR_VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        icon="mdi:cloud",
    ),
    SensorEntityDescription(
        key="allpollu",
        name=ATTR_FOOBOT_INDEX,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
    ),
)

SCAN_INTERVAL = timedelta(minutes=10)
PARALLEL_UPDATES = 1

TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_TOKEN): cv.string, vol.Required(CONF_USERNAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the devices associated with the account."""
    token: str = config[CONF_TOKEN]
    username: str = config[CONF_USERNAME]

    client = FoobotClient(
        token, username, async_get_clientsession(hass), timeout=TIMEOUT
    )
    entities: list[FoobotSensor] = []
    try:
        devices: list[dict[str, Any]] = await client.get_devices()
        _LOGGER.debug("The following devices were found: %s", devices)
        for device in devices:
            foobot_data = FoobotData(client, device["uuid"])
            entities.extend(
                [
                    FoobotSensor(foobot_data, device, description)
                    for description in SENSOR_TYPES
                ]
            )
    except (
        aiohttp.client_exceptions.ClientConnectorError,
        TimeoutError,
        FoobotClient.TooManyRequests,
        FoobotClient.InternalError,
    ) as err:
        _LOGGER.exception("Failed to connect to foobot servers")
        raise PlatformNotReady from err
    except FoobotClient.ClientError:
        _LOGGER.error("Failed to fetch data from foobot servers")
        return
    async_add_entities(entities, True)


class FoobotSensor(SensorEntity):
    """Implementation of a Foobot sensor."""

    def __init__(
        self,
        data: FoobotData,
        device: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.foobot_data = data

        self._attr_name = f"Foobot {device['name']} {description.name}"
        self._attr_unique_id = f"{device['uuid']}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the device."""
        return self.foobot_data.data.get(self.entity_description.key)

    async def async_update(self) -> None:
        """Get the latest data."""
        await self.foobot_data.async_update()


class FoobotData:
    """Get data from Foobot API."""

    def __init__(self, client: FoobotClient, uuid: str) -> None:
        """Initialize the data object."""
        self._client = client
        self._uuid = uuid
        self.data: dict[str, float] = {}

    @Throttle(SCAN_INTERVAL)
    async def async_update(self) -> bool:
        """Get the data from Foobot API."""
        interval = SCAN_INTERVAL.total_seconds()
        try:
            response: list[dict[str, Any]] = await self._client.get_last_data(
                self._uuid, interval, interval + 1
            )
        except (
            aiohttp.client_exceptions.ClientConnectorError,
            TimeoutError,
            self._client.TooManyRequests,
            self._client.InternalError,
        ):
            _LOGGER.debug("Couldn't fetch data")
            return False
        _LOGGER.debug("The data response is: %s", response)
        self.data = {k: round(v, 1) for k, v in response[0].items()}
        return True
