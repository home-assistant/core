"""Config flow for UpCloud."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
import requests.exceptions
import upcloud_api

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class UpCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """UpCloud config flow."""

    VERSION = 1

    username: str
    password: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated flow."""
        if user_input is None:
            return self._async_show_form(step_id="user")

        await self.async_set_unique_id(user_input[CONF_USERNAME])

        if errors := await self._async_validate_input(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        ):
            return self._async_show_form(
                step_id="user", user_input=user_input, errors=errors
            )

        self._abort_if_unique_id_configured(
            updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
        )
        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (
                errors := await self._async_validate_input(
                    reauth_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            ):
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
            ),
            description_placeholders={"username": reauth_entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def _async_validate_input(
        self, username: str, password: str
    ) -> dict[str, str]:
        """Validate the credentials and return form errors."""
        manager = upcloud_api.CloudManager(username, password)

        errors = {}
        try:
            await self.hass.async_add_executor_job(manager.authenticate)
        except upcloud_api.UpCloudAPIError:
            errors["base"] = "invalid_auth"
            _LOGGER.debug("invalid_auth", exc_info=True)
        except requests.exceptions.RequestException:
            errors["base"] = "cannot_connect"
            _LOGGER.debug("cannot_connect", exc_info=True)
        return errors

    @callback
    def _async_show_form(
        self,
        step_id: str,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show our form."""
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    probatio.Required(
                        probatio.Secret(CONF_PASSWORD),
                        default=user_input.get(CONF_PASSWORD, ""),
                    ): str,
                }
            ),
            errors=errors or {},
        )
