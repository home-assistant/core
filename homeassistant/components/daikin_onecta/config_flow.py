"""Config flow for the Daikin platform."""
import logging
from collections.abc import Mapping
from typing import Any

import jwt
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import BooleanSelector
from homeassistant.helpers.selector import NumberSelector
from homeassistant.helpers.selector import NumberSelectorConfig
from homeassistant.helpers.selector import TimeSelector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_HOMEKIT_FAN_MODE_ALIASES
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for Daikin Onecta ."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Daikin Onecta options flow."""
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "high_scan_interval",
                        default=self.options.get("high_scan_interval", 10),
                    ): NumberSelector(
                        NumberSelectorConfig(min=5, max=240, step=1),
                    ),
                    vol.Required(
                        "low_scan_interval",
                        default=self.options.get("low_scan_interval", 30),
                    ): NumberSelector(
                        NumberSelectorConfig(min=10, max=240, step=1),
                    ),
                    vol.Required(
                        "high_scan_start",
                        default=self.options.get("high_scan_start", "07:00:00"),
                    ): TimeSelector(),
                    vol.Required(
                        "low_scan_start",
                        default=self.options.get("low_scan_start", "22:00:00"),
                    ): TimeSelector(),
                    vol.Required(
                        "scan_ignore",
                        default=self.options.get("scan_ignore", 30),
                    ): NumberSelector(
                        NumberSelectorConfig(min=20, max=300, step=1),
                    ),
                    vol.Required(
                        CONF_HOMEKIT_FAN_MODE_ALIASES,
                        default=self.options.get(CONF_HOMEKIT_FAN_MODE_ALIASES, False),
                    ): BooleanSelector(),
                }
            ),
            errors={},
        )


class FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow."""

    # See https://developers.home-assistant.io/docs/core/platform/application_credentials/
    # and https://developer.cloud.daikineurope.com/docs/b0dffcaa-7b51-428a-bdff-a7c8a64195c0/getting_started
    VERSION = 1
    MINOR_VERSION = 2
    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "openid onecta:basic.integration offline_access"}

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        try:
            unique_id = jwt.decode(data["token"]["access_token"], options={"verify_signature": False})["sub"]
        except (jwt.DecodeError, KeyError):
            _LOGGER.exception("Failed to decode JWT")
            return self.async_abort(reason="invalid_token")

        await self.async_set_unique_id(unique_id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=data)
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Options callback for Daikin Onecta."""
        return OptionsFlowHandler(config_entry)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle a discovered Daikin device via mDNS."""
        _LOGGER.info(
            "Daikin device discovered via mDNS: host=%s hostname=%s type=%s properties=%s",
            discovery_info.host,
            discovery_info.hostname,
            discovery_info.type,
            discovery_info.properties,
        )

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        hostname = discovery_info.hostname
        if not hostname:
            return self.async_abort(reason="unknown")

        # Strip trailing dot and .local suffix for a clean display name.
        # e.g. "altherma4-a1b2-c3d4.local." -> "altherma4-a1b2-c3d4"
        hostname = hostname.rstrip(".")
        hostname = hostname.removesuffix(".local")

        self.context["title_placeholders"] = {"name": hostname}

        return await self.async_step_user()
