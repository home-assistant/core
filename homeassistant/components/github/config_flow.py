"""Config flow for GitHub integration."""
import logging

from github import Github, GithubException, Repository
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL

from .const import CONF_REPOSITORY, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_REPOSITORY): str,
        vol.Optional(CONF_URL): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    url = data[CONF_URL]

    try:
        if url:
            github = Github(data[CONF_ACCESS_TOKEN], base_url=url)
        else:
            github = Github(data[CONF_ACCESS_TOKEN])
    except GithubException.BadCredentialsException:
        raise InvalidAuth
    except GithubException.GithubException:
        raise CannotConnect

    repository: Repository = github.get_repo(data[CONF_REPOSITORY])

    return {"title": repository.name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GitHub."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
