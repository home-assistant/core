"""Config flow for the Daikin platform."""

from collections.abc import Mapping
import logging
from typing import Any, override

import jwt
import probatio

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    TimeSelector,
)

from .const import CONF_HOMEKIT_FAN_MODE_ALIASES, DOMAIN

_LOGGER = logging.getLogger(__name__)
OAUTH_SCOPES = [
    "openid",
    "onecta:basic.integration",
    "offline_access",
]


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for Daikin Onecta ."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Daikin Onecta options flow."""
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            if user_input["high_scan_interval"] <= user_input["low_scan_interval"]:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        "high_scan_interval",
                        default=self.options.get("high_scan_interval", 10),
                    ): NumberSelector(
                        NumberSelectorConfig(min=5, max=240, step=1),
                    ),
                    probatio.Required(
                        "low_scan_interval",
                        default=self.options.get("low_scan_interval", 30),
                    ): NumberSelector(
                        NumberSelectorConfig(min=10, max=240, step=1),
                    ),
                    probatio.Required(
                        "high_scan_start",
                        default=self.options.get("high_scan_start", "07:00:00"),
                    ): TimeSelector(),
                    probatio.Required(
                        "low_scan_start",
                        default=self.options.get("low_scan_start", "22:00:00"),
                    ): TimeSelector(),
                    probatio.Required(
                        "scan_ignore",
                        default=self.options.get("scan_ignore", 30),
                    ): NumberSelector(
                        NumberSelectorConfig(min=20, max=300, step=1),
                    ),
                    probatio.Required(
                        CONF_HOMEKIT_FAN_MODE_ALIASES,
                        default=self.options.get(CONF_HOMEKIT_FAN_MODE_ALIASES, False),
                    ): BooleanSelector(),
                }
            ),
            errors={"base": "high_scan_interval_greater_than_low"}
            if user_input is not None
            else {},
        )


class FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow."""

    # See https://developers.home-assistant.io/docs/core/platform/application_credentials/
    VERSION = 1
    MINOR_VERSION = 2
    DOMAIN = DOMAIN

    @property
    @override
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH_SCOPES)}

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        try:
            unique_id = jwt.decode(
                data["token"]["access_token"], options={"verify_signature": False}
            )["sub"]
        except jwt.DecodeError, KeyError:
            _LOGGER.exception("Failed to decode JWT")
            return self.async_abort(reason="invalid_token")

        await self.async_set_unique_id(unique_id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=probatio.Schema({}),
            )
        return await self.async_step_user()

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Options callback for Daikin Onecta."""
        return OptionsFlowHandler(config_entry)
