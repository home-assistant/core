"""Support for Home Panel."""
import logging
from typing import Any, Dict

from homepanelapi.api import HomePanelApi
import voluptuous as vol

from homeassistant.components.home_panel.const import (
    CONF_CARD,
    CONF_COMMAND,
    CONF_PAGE,
    DATA_HOME_PANEL_CLIENT,
    DATA_HOST,
    DATA_PASSWORD,
    DATA_PORT,
    DATA_USERNAME,
    DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PAGE): cv.string,
        vol.Required(CONF_CARD): cv.string,
        vol.Required(CONF_COMMAND): cv.string,
    }
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Home Panel components."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Home Panel from a config entry."""
    home_panel_api = HomePanelApi(
        entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_SSL]
    )

    hass.data.setdefault(DOMAIN, {})[DATA_HOME_PANEL_CLIENT] = home_panel_api
    hass.data.setdefault(DOMAIN, {})[DATA_HOST] = entry.data[CONF_HOST]
    hass.data.setdefault(DOMAIN, {})[DATA_PORT] = entry.data[CONF_PORT]
    hass.data.setdefault(DOMAIN, {})[DATA_USERNAME] = entry.data[CONF_USERNAME]
    hass.data.setdefault(DOMAIN, {})[DATA_PASSWORD] = entry.data[CONF_PASSWORD]

    # Setup sensors
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    async def send_command(call) -> None:
        """Service call to send a command to Home Panel."""
        authenticated = await home_panel_api.async_authenticate(
            hass.data[DOMAIN][DATA_USERNAME], hass.data[DOMAIN][DATA_PASSWORD]
        )
        if authenticated:
            result = await home_panel_api.async_send_command(
                call.data.get(CONF_PAGE),
                call.data.get(CONF_CARD),
                call.data.get(CONF_COMMAND),
            )
            if not result:
                _LOGGER.error("No result for API call")
            else:
                _LOGGER.info(result)

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, send_command, schema=SERVICE_SEND_COMMAND_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Unload Home Panel config entry."""
    hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)

    # Unload sensors
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    del hass.data[DOMAIN]

    return True


class HomePanelEntity(Entity):
    """Defines a base Home Panel entity."""

    def __init__(
        self, home_panel_api, username: str, password: str, name: str, icon: str
    ) -> None:
        """Initialize the Home Panel entity."""
        self._name = name
        self._icon = icon
        self._available = True
        self.home_panel_api = home_panel_api
        self.username = username
        self.password = password

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_update(self) -> None:
        """Update Home Panel entity."""
        if await self._home_panel_update():
            self._available = True
        else:
            if self._available:
                _LOGGER.debug(
                    "An error occurred while updating Home Panel sensor.", exc_info=True
                )
            self._available = False

    async def _home_panel_update(self) -> None:
        """Update Home Panel entity."""
        raise NotImplementedError()


class HomePanelDeviceEntity(HomePanelEntity):
    """Defines a Home Panel device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Home Panel instance."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self.hass.data[DOMAIN][DATA_USERNAME],
                    self.hass.data[DOMAIN][DATA_HOST],
                    self.hass.data[DOMAIN][DATA_PORT],
                )
            },
            "name": "Home Panel",
            "manufacturer": "Timmo",
        }
