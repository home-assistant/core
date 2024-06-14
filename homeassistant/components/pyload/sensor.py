"""Support for monitoring pyLoad."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
import logging
from time import monotonic
from typing import Any

from aiohttp import CookieJar
from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=15)


class PyLoadSensorEntity(StrEnum):
    """pyLoad Sensor Entities."""

    SPEED = "speed"


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=PyLoadSensorEntity.SPEED,
        name="Speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=1,
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["speed"]): vol.All(
            cv.ensure_list, [vol.In(PyLoadSensorEntity)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the pyLoad sensors."""
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    protocol = "https" if config[CONF_SSL] else "http"
    name = config[CONF_NAME]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    url = f"{protocol}://{host}:{port}/"

    session = async_create_clientsession(
        hass,
        verify_ssl=False,
        cookie_jar=CookieJar(unsafe=True),
    )
    pyloadapi = PyLoadAPI(session, api_url=url, username=username, password=password)
    try:
        await pyloadapi.login()
    except CannotConnect as conn_err:
        raise PlatformNotReady(
            "Unable to connect and retrieve data from pyLoad API"
        ) from conn_err
    except ParserError as e:
        raise PlatformNotReady("Unable to parse data from pyLoad API") from e
    except InvalidAuth as e:
        raise PlatformNotReady(
            f"Authentication failed for {config[CONF_USERNAME]}, check your login credentials"
        ) from e

    async_add_entities(
        (
            PyLoadSensor(
                api=pyloadapi, entity_description=description, client_name=name
            )
            for description in SENSOR_DESCRIPTIONS
        ),
        True,
    )


class PyLoadSensor(SensorEntity):
    """Representation of a pyLoad sensor."""

    def __init__(
        self, api: PyLoadAPI, entity_description: SensorEntityDescription, client_name
    ) -> None:
        """Initialize a new pyLoad sensor."""
        self._attr_name = f"{client_name} {entity_description.name}"
        self.type = entity_description.key
        self.api = api
        self.entity_description = entity_description
        self._attr_available = False
        self.data: dict[str, Any] = {}

    async def async_update(self) -> None:
        """Update state of sensor."""
        try:
            start = monotonic()
            status = await self.api.get_status()
            self.data = status.to_dict()

            _LOGGER.debug(
                "Finished fetching pyload data in %.3f seconds",
                monotonic() - start,
            )
        except InvalidAuth:
            _LOGGER.info("Authentication failed, trying to reauthenticate")
            try:
                await self.api.login()
            except InvalidAuth:
                _LOGGER.error(
                    "Authentication failed for %s, check your login credentials",
                    self.api.username,
                )
                return
            else:
                _LOGGER.info(
                    "Unable to retrieve data due to cookie expiration "
                    "but re-authentication was successful"
                )
                return
            finally:
                self._attr_available = False

        except CannotConnect:
            _LOGGER.debug("Unable to connect and retrieve data from pyLoad API")
            self._attr_available = False
            return
        except ParserError:
            _LOGGER.error("Unable to parse data from pyLoad API")
            self._attr_available = False
            return

        self._attr_available = True

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.data.get(self.entity_description.key)
