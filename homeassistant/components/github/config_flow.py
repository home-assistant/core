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
from homeassistant.core import callback

from .const import (
    CONF_CLONES,
    CONF_ISSUES_PRS,
    CONF_LATEST_COMMIT,
    CONF_LATEST_RELEASE,
    CONF_REPOSITORY,
    CONF_VIEWS,
)
from .const import DOMAIN  # pylint: disable=unused-import

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

    return {"title": repository.attributes.get("name")}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GitHub."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._repository = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input[CONF_REPOSITORY])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotFindRepo:
                errors["base"] = "cannot_find_repo"
            except InvalidAuth:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        errors = {}

        if user_input is not None:
            if user_input.get(CONF_REPOSITORY) is not None:
                self._repository = user_input[CONF_REPOSITORY]
                # pylint: disable=no-member
                self.context["title_placeholders"] = {
                    "repository": user_input[CONF_REPOSITORY]
                }

            elif user_input.get(CONF_ACCESS_TOKEN) is not None:
                user_input[CONF_REPOSITORY] = self._repository

                await self.async_set_unique_id(user_input[CONF_REPOSITORY])

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

        return self.async_show_form(
            step_id="reauth", data_schema=REAUTH_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Options callback for GitHub."""
        return GitHubOptionsFlowHandler(config_entry)


class GitHubOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for GitHub."""

    def __init__(self, config_entry):
        """Initialize GitHub options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        try:
            github = GitHub(self.config_entry.data[CONF_ACCESS_TOKEN])
            repository = await github.get_repo(self.config_entry.data[CONF_REPOSITORY])
        except (AIOGitHubAPIAuthenticationException, AIOGitHubAPIException):
            return self.async_abort(reason="connection_error")

        schema = {
            vol.Optional(
                CONF_LATEST_COMMIT,
                default=self.config_entry.options.get(CONF_LATEST_COMMIT, True),
            ): bool,
            vol.Optional(
                CONF_LATEST_RELEASE,
                default=self.config_entry.options.get(CONF_LATEST_RELEASE, False),
            ): bool,
            vol.Optional(
                CONF_ISSUES_PRS,
                default=self.config_entry.options.get(CONF_ISSUES_PRS, False),
            ): bool,
        }

        if repository.attributes.get("permissions").get("push") is True:
            schema = {
                vol.Optional(
                    CONF_CLONES,
                    default=self.config_entry.options.get(CONF_CLONES, False),
                ): bool,
                **schema,
                vol.Optional(
                    CONF_VIEWS,
                    default=self.config_entry.options.get(CONF_VIEWS, False),
                ): bool,
            }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(schema),)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class CannotFindRepo(exceptions.HomeAssistantError):
    """Error to indicate repo cannot be found."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
