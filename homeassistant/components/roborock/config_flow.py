"""Config flow for Roborock."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from roborock.api import RoborockApiClient
from roborock.containers import UserData
from roborock.exceptions import (
    RoborockAccountDoesNotExist,
    RoborockException,
    RoborockInvalidCode,
    RoborockInvalidEmail,
    RoborockUrlException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BASE_URL,
    CONF_ENTRY_CODE,
    CONF_INCLUDE_SHARED,
    CONF_USER_DATA,
    DEFAULT_DRAWABLES,
    DEFAULT_INCLUDE_SHARED,
    DEFAULT_SIZES,
    DOMAIN,
    DRAWABLES,
    MAPS,
    SIZES,
)

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roborock."""

    VERSION = 1
    reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._client: RoborockApiClient | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            self._username = username
            _LOGGER.debug("Requesting code for Roborock account")
            self._client = RoborockApiClient(username)
            errors = await self._request_code()
            if not errors:
                return await self.async_step_code()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USERNAME): str}),
            errors=errors,
        )

    async def _request_code(self) -> dict:
        assert self._client
        errors: dict[str, str] = {}
        try:
            await self._client.request_code()
        except RoborockAccountDoesNotExist:
            errors["base"] = "invalid_email"
        except RoborockUrlException:
            errors["base"] = "unknown_url"
        except RoborockInvalidEmail:
            errors["base"] = "invalid_email_format"
        except RoborockException as ex:
            _LOGGER.exception(ex)
            errors["base"] = "unknown_roborock"
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(ex)
            errors["base"] = "unknown"
        return errors

    async def async_step_code(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        assert self._client
        assert self._username
        if user_input is not None:
            code = user_input[CONF_ENTRY_CODE]
            _LOGGER.debug("Logging into Roborock account using email provided code")
            try:
                login_data = await self._client.code_login(code)
            except RoborockInvalidCode:
                errors["base"] = "invalid_code"
            except RoborockException as ex:
                _LOGGER.exception(ex)
                errors["base"] = "unknown_roborock"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception(ex)
                errors["base"] = "unknown"
            else:
                if self.reauth_entry is not None:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry,
                        data={
                            **self.reauth_entry.data,
                            CONF_USER_DATA: login_data.as_dict(),
                        },
                    )
                    return self.async_abort(reason="reauth_successful")
                return self._create_entry(self._client, self._username, login_data)

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required(CONF_ENTRY_CODE): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._username = entry_data[CONF_USERNAME]
        assert self._username
        self._client = RoborockApiClient(self._username)
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._request_code()
            if not errors:
                return await self.async_step_code()
        return self.async_show_form(step_id="reauth_confirm", errors=errors)

    def _create_entry(
        self, client: RoborockApiClient, username: str, user_data: UserData
    ) -> FlowResult:
        """Finished config flow and create entry."""
        return self.async_create_entry(
            title=username,
            data={
                CONF_USERNAME: username,
                CONF_USER_DATA: user_data.as_dict(),
                CONF_BASE_URL: client.base_url,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return RoborockOptionsFlowHandler(config_entry)


class RoborockOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Handle an option flow for Roborock."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(step_id="init", menu_options=[DOMAIN, MAPS])

    async def async_step_roborock(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options domain wide."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self.config_entry.options, **user_input}
            )
        return self.async_show_form(
            step_id=DOMAIN,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INCLUDE_SHARED,
                        default=self.config_entry.options.get(
                            CONF_INCLUDE_SHARED, DEFAULT_INCLUDE_SHARED
                        ),
                    ): bool
                }
            ),
        )

    async def async_step_maps(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Open the menu for the map options."""
        return self.async_show_menu(step_id=MAPS, menu_options=[DRAWABLES, SIZES])

    async def async_step_sizes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the map object size options."""
        if user_input is not None:
            new_sizes = {
                SIZES: {**self.config_entry.options.get(SIZES, {}), **user_input}
            }
            return self.async_create_entry(
                title="", data={**self.config_entry.options, **new_sizes}
            )
        data_schema = {}
        for size, default_value in DEFAULT_SIZES.items():
            data_schema[
                vol.Required(
                    size.value,
                    default=self.config_entry.options.get(SIZES, {}).get(
                        size, default_value
                    ),
                )
            ] = vol.All(vol.Coerce(float), vol.Range(min=0))
        return self.async_show_form(
            step_id=SIZES,
            data_schema=vol.Schema(data_schema),
        )

    async def async_step_drawables(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the map object drawable options."""
        if user_input is not None:
            new_drawables = {
                DRAWABLES: {
                    **self.config_entry.options.get(DRAWABLES, {}),
                    **user_input,
                }
            }
            return self.async_create_entry(
                title="", data={**self.config_entry.options, **new_drawables}
            )
        data_schema = {}
        for drawable, default_value in DEFAULT_DRAWABLES.items():
            data_schema[
                vol.Required(
                    drawable.value,
                    default=self.config_entry.options.get(DRAWABLES, {}).get(
                        drawable, default_value
                    ),
                )
            ] = bool
        return self.async_show_form(
            step_id=DRAWABLES,
            data_schema=vol.Schema(data_schema),
        )
