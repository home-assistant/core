"""Config flow for GitHub integration."""
import logging

from aiogithubapi import (
    AIOGitHubAPIAuthenticationException,
    AIOGitHubAPIException,
    GitHub,
)
from aiogithubapi.objects.repository import AIOGitHubAPIRepository
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import CONF_REPOSITORY, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_ACCESS_TOKEN): str, vol.Required(CONF_REPOSITORY): str}
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    try:
        github = GitHub(data[CONF_ACCESS_TOKEN])
        repository: AIOGitHubAPIRepository = await github.get_repo(
            data[CONF_REPOSITORY]
        )
        if repository is None:
            raise CannotFindRepo
    except AIOGitHubAPIAuthenticationException:
        raise InvalidAuth
    except AIOGitHubAPIException:
        raise CannotConnect

    return {"title": repository.full_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GitHub."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.access_token = None
        self.repository = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotFindRepo:
                errors["base"] = "cannot_find_repo"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        errors = {}

        if user_input is None:
            user_input = {}

        if user_input.get(CONF_ACCESS_TOKEN) is None and self.access_token is not None:
            user_input[CONF_ACCESS_TOKEN] = self.access_token
        else:
            self.access_token = user_input[CONF_ACCESS_TOKEN]

        if user_input.get(CONF_REPOSITORY) is None and self.repository is not None:
            user_input[CONF_REPOSITORY] = self.repository
        else:
            self.repository = user_input[CONF_REPOSITORY]

        if self.context is None:
            self.context = {}
        # pylint: disable=no-member
        self.context["title_placeholders"] = {
            "name": user_input[CONF_REPOSITORY],
        }
        try:
            await validate_input(self.hass, user_input)
            for entry in self._async_current_entries():
                if entry.unique_id == self.unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry, data=user_input,
                    )
                    return self.async_abort(reason="reauth_successful")
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except CannotFindRepo:
            errors["base"] = "cannot_find_repo"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth", data_schema=REAUTH_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class CannotFindRepo(exceptions.HomeAssistantError):
    """Error to indicate repo cannot be found."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
