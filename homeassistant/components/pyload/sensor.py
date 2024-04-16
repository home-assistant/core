"""Support for monitoring pyLoad."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import CookieJar
from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
from pyloadapi.types import StatusServerResponse
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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=15)

SENSOR_TYPES = {
    "speed": SensorEntityDescription(
        key="speed",
        name="Speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
    )
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["speed"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
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
    monitored_types = config[CONF_MONITORED_VARIABLES]
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
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_exception",
        ) from conn_err
    except ParserError as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="parse_exception",
        ) from e
    except InvalidAuth as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_exception",
            translation_placeholders={CONF_USERNAME: config[CONF_USERNAME]},
        ) from e

    devices = []
    for ng_type in monitored_types:
        new_sensor = PyLoadSensor(
            api=pyloadapi, sensor_type=SENSOR_TYPES[ng_type], client_name=name
        )
        devices.append(new_sensor)

    async_add_entities(devices, True)


class PyLoadSensor(SensorEntity):
    """Representation of a pyLoad sensor."""

    def __init__(
        self, api: PyLoadAPI, sensor_type: SensorEntityDescription, client_name
    ) -> None:
        """Initialize a new pyLoad sensor."""
        self._attr_name = f"{client_name} {sensor_type.name}"
        self.type = sensor_type.key
        self.api = api
        self.entity_description = sensor_type
        self.data: StatusServerResponse

    async def async_update(self) -> None:
        """Update state of sensor."""
        try:
            self.data = await self.api.get_status()
        except InvalidAuth:
            _LOGGER.info("Authentication failed, trying to reauthenticate")
            try:
                await self.api.login()
            except InvalidAuth as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_exception",
                    translation_placeholders={CONF_USERNAME: self.api.username},
                ) from e
            else:
                raise UpdateFailed(
                    "Unable to retrieve data due to cookie expiration but re-authentication was successful."
                )
        except CannotConnect as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from pyLoad API"
            ) from e
        except ParserError as e:
            raise UpdateFailed("Unable to parse data from pyLoad API") from e
        else:
            if self.data is None:
                _LOGGER.debug(
                    "Update of %s requested, but no status is available", self.name
                )
                return

        if (value := getattr(self.data, self.type, None)) is None:
            _LOGGER.warning("Unable to locate value for %s", self.type)
            return

        if "speed" in self.type and value > 0:
            # Convert download rate from Bytes/s to MBytes/s
            self._attr_native_value = round(value / 2**20, 2)
        else:
            self._attr_native_value = value
