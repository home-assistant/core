"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""
from __future__ import annotations

import logging

from aiohttp import ClientResponseError
from incomfortclient import Gateway as InComfortGateway
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "incomfort"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Inclusive(CONF_USERNAME, "credentials"): cv.string,
                vol.Inclusive(CONF_PASSWORD, "credentials"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = (
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.CLIMATE,
)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Create an Intergas InComfort/Intouch system."""
    incomfort_data = hass.data[DOMAIN] = {}

    credentials = dict(hass_config[DOMAIN])
    hostname = credentials.pop(CONF_HOST)

    client = incomfort_data["client"] = InComfortGateway(
        hostname, **credentials, session=async_get_clientsession(hass)
    )

    try:
        heaters = incomfort_data["heaters"] = list(await client.heaters)
    except ClientResponseError as err:
        _LOGGER.warning("Setup failed, check your configuration, message is: %s", err)
        return False

    for heater in heaters:
        await heater.update()

    for platform in PLATFORMS:
        hass.async_create_task(
            async_load_platform(hass, platform, DOMAIN, {}, hass_config)
        )

    return True


class IncomfortEntity(Entity):
    """Base class for all InComfort entities."""

    def __init__(self) -> None:
        """Initialize the class."""
        self._name: str | None = None
        self._unique_id: str | None = None

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return self._name


class IncomfortChild(IncomfortEntity):
    """Base class for all InComfort entities (excluding the boiler)."""

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(async_dispatcher_connect(self.hass, DOMAIN, self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False
