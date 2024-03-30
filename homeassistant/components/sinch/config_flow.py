"""Config flow for sinch integration."""

from __future__ import annotations

import logging

from clx.xms.client import Client
from clx.xms.exceptions import UnauthorizedException, UnexpectedResponseException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_SENDER
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEFAULT_RECIPIENTS,
    CONF_SERVICE_PLAN_ID,
    DEFAULT_NAME,
    DEFAULT_SENDER,
    DOMAIN,
    MAX_SENDER_LENGTH,
)

_LOGGER = logging.getLogger(__name__)


def check_client_connection(service_plan_id: str, api_key: str):
    """Check client connection."""
    client = Client(service_plan_id, api_key)
    batches = client.fetch_batches()
    batches.get(0)
    return True


class SinchFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sinch."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: ConfigType | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SERVICE_PLAN_ID])
            self._abort_if_unique_id_configured()

            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                }
            )
            if not (
                error := await self._async_try_connect(
                    user_input[CONF_SERVICE_PLAN_ID], user_input[CONF_API_KEY]
                )
            ):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            errors["base"] = error

        else:
            user_input = {
                CONF_NAME: DEFAULT_NAME,
                CONF_SERVICE_PLAN_ID: "",
                CONF_API_KEY: "",
            }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(
                        CONF_SERVICE_PLAN_ID, default=user_input[CONF_SERVICE_PLAN_ID]
                    ): str,
                    vol.Required(CONF_API_KEY, default=user_input[CONF_API_KEY]): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "token_url": "https://dashboard.sinch.com/sms/api/services",
                "component_url": ("https://www.home-assistant.io/integrations/sinch/"),
            },
        )

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        _LOGGER.warning(
            "Configuration of the Sinch integration in YAML is deprecated and "
            "will be removed in a future release; Your existing configuration "
            "has been imported into the UI automatically and can be safely removed "
            "from your configuration.yaml file"
        )
        entries = self._async_current_entries()
        if any(
            x.data[CONF_API_KEY] == import_config[CONF_API_KEY]
            and x.data[CONF_SERVICE_PLAN_ID] == import_config[CONF_SERVICE_PLAN_ID]
            for x in entries
        ):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return SinchOptionsFlowHandler(config_entry)

    async def _async_try_connect(
        self, service_plan_id: str, api_key: str
    ) -> str | None:
        """Try connecting to Sinch API."""
        try:
            await self.hass.async_add_executor_job(
                check_client_connection, service_plan_id, api_key
            )
        except UnauthorizedException as ex:
            _LOGGER.error("Caught UnauthorizedException: %s", ex)
            return "invalid_auth"
        except UnexpectedResponseException as ex:
            _LOGGER.error("Caught UnexpectedResponseException: %s", ex)
            return "cannot_connect"
        return None


class SinchOptionsFlowHandler(OptionsFlow):
    """Handle options flow for sinch."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: ConfigType | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}

        if user_input is not None:
            if recipients := user_input.get(CONF_DEFAULT_RECIPIENTS, ""):
                user_input[CONF_DEFAULT_RECIPIENTS] = self._sanitize_recipients(
                    recipients
                )

            if len(str(user_input.get(CONF_SENDER))) > MAX_SENDER_LENGTH:
                errors["base"] = "invalid_sender"

            if len(errors) == 0:
                return self.async_create_entry(
                    title="",
                    data=user_input,
                )
            options = user_input
        else:
            options = self.config_entry.options.copy()
        default_recipients = options.get(CONF_DEFAULT_RECIPIENTS) or []

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SENDER,
                        default=options.get(CONF_SENDER, DEFAULT_SENDER),
                    ): str,
                    vol.Optional(
                        CONF_DEFAULT_RECIPIENTS,
                        default="\n".join(default_recipients),
                    ): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEL,
                            multiline=True,
                            autocomplete="tel",
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    def _sanitize_recipients(self, recipients: str) -> list[str]:
        return [
            num.strip()
            for num in recipients.replace("\n", ",").split(",")
            if num.strip()
        ]
