"""Config flow for qBittorrent integration."""
import logging

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

from .client import create_client
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass, data):
    """Validate user or import input."""
    errors = {}
    try:
        await hass.async_add_executor_job(
            create_client,
            data[CONF_URL],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
    except LoginRequired:
        errors["base"] = "invalid_auth"

    except RequestException as err:
        errors["base"] = "cannot_connect"
        _LOGGER.error("Connection failed - %s", err)
    return errors


class QBittorrentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for qbittorrent."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize qbittorrent config flow."""
        self._data = None
        self._title = None

    async def async_step_import(self, device_config):
        """Import a configuration.yaml config."""
        data = {}

        data[CONF_URL] = device_config.get(CONF_URL)
        data[CONF_USERNAME] = device_config.get(CONF_USERNAME)
        data[CONF_PASSWORD] = device_config.get(CONF_PASSWORD)

        errors = await validate_input(self.hass, data)
        if not errors:
            self._data = data
            self._title = data[CONF_URL]
            return await self.async_step_import_confirm()

        return self.async_abort(reason=errors["base"])

    async def async_step_import_confirm(self, user_input=None):
        """Confirm the user wants to import the config entry."""
        if user_input is None:
            return self.async_show_form(
                step_id="import_confirm",
                description_placeholders={"id": self._title},
            )

        await self.async_set_unique_id(self._data[CONF_URL])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._data[CONF_URL],
            data={
                CONF_USERNAME: self._data[CONF_USERNAME],
                CONF_PASSWORD: self._data[CONF_PASSWORD],
                CONF_URL: self._data[CONF_URL],
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_URL])
            self._abort_if_unique_id_configured()

            _LOGGER.debug(
                "Configuring user: %s - Password hidden", user_input[CONF_USERNAME]
            )

            errors = await validate_input(self.hass, user_input)

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_URL],
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_URL: user_input[CONF_URL],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
