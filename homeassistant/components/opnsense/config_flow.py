"""Config flow for OPNsense."""

import logging
from typing import Any

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
from requests.exceptions import ConnectionError as requestsConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACES, DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class OPNsenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """OPNsense config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    data: Any | None = None

    async def _show_setup_form(
        self,
        user_input: (dict[Any, Any] | None) = None,
        errors: (dict[Any, Any] | None) = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        description_placeholders = {}
        description_placeholders["doc_url"] = (
            "https://www.home-assistant.io/integrations/opnsense/"
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, 80)
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                    ): str,
                    vol.Required(
                        CONF_API_SECRET, default=user_input.get(CONF_API_SECRET, "")
                    ): str,
                    vol.Required(
                        CONF_SSL, default=user_input.get(CONF_SSL, False)
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, False)
                    ): bool,
                    vol.Optional(CONF_TRACKER_INTERFACES): str,
                }
            ),
            errors=errors or {},
            description_placeholders=description_placeholders,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user step."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form(user_input, None)

        await self.async_set_unique_id(user_input[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        if not user_input.get(CONF_URL):
            protocol = "https" if user_input[CONF_SSL] else "http"
            url = f"{protocol}://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/api"
            user_input[CONF_URL] = url

        tracker_interfaces = user_input.get(CONF_TRACKER_INTERFACES, None)
        if isinstance(tracker_interfaces, str):
            tracker_interfaces = tracker_interfaces.replace(" ", "").split(",")
            user_input[CONF_TRACKER_INTERFACES] = tracker_interfaces

        api_data = {
            CONF_API_KEY: user_input[CONF_API_KEY],
            CONF_API_SECRET: user_input[CONF_API_SECRET],
            "base_url": user_input[CONF_URL],
            "verify_cert": user_input[CONF_VERIFY_SSL],
        }
        interfaces_client = diagnostics.InterfaceClient(**api_data)

        try:
            # Check connection
            await self.hass.async_add_executor_job(interfaces_client.get_arp)

            if tracker_interfaces:
                # Verify that specified tracker interfaces are valid
                netinsight_client = diagnostics.NetworkInsightClient(**api_data)
                interfaces = await self.hass.async_add_executor_job(
                    netinsight_client.get_interfaces
                )
                interfaces_names = list(interfaces.values())
                for interface in tracker_interfaces:
                    if interface not in interfaces_names:
                        errors["base"] = "invalid_interface"
                        return await self._show_setup_form(user_input, errors)

                return self.async_create_entry(title="OPNsense", data=user_input)

        except (APIException, requestsConnectionError):
            _LOGGER.error("Error connecting to the OPNsense router")
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return await self._show_setup_form(user_input, errors)

    async def async_step_import(
        self, import_config: (dict[str, Any] | None)
    ) -> ConfigFlowResult:
        """Import a config entry."""
        return await self.async_step_user(import_config)
