"""Config flow for OPNsense."""

import asyncio
import logging
from typing import Any

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
from requests.exceptions import ConnectionError as requestsConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    CONF_API_SECRET,
    CONF_AVAILABLE_INTERFACES,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
    OPNSENSE_DATA,
)
from .types import APIData, Interfaces

_LOGGER = logging.getLogger(__name__)


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """OPNsense config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize OPNsense config flow."""
        self.available_interfaces: Interfaces | None = None

    async def _show_setup_form(
        self,
        user_input: dict[Any, Any] | None = None,
        errors: dict[Any, Any] | None = None,
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
                    vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): str,
                    vol.Required(
                        CONF_API_KEY,
                        default=user_input.get(CONF_API_KEY, ""),
                    ): str,
                    vol.Required(
                        CONF_API_SECRET, default=user_input.get(CONF_API_SECRET, "")
                    ): str,
                    vol.Required(
                        CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, False)
                    ): bool,
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

        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

        tracker_interfaces = user_input.get(CONF_TRACKER_INTERFACES, None)
        if isinstance(tracker_interfaces, str):
            tracker_interfaces = tracker_interfaces.replace(" ", "").split(",")
            user_input[CONF_TRACKER_INTERFACES] = tracker_interfaces

        api_data: APIData = {
            "api_key": user_input[CONF_API_KEY],
            "api_secret": user_input[CONF_API_SECRET],
            "base_url": user_input[CONF_URL],
            "verify_cert": user_input[CONF_VERIFY_SSL],
        }

        try:
            await asyncio.gather(
                self._async_check_connection(api_data),
                self._async_get_available_interfaces(api_data),
            )
            if tracker_interfaces and self.available_interfaces:
                # Verify that specified tracker interfaces are valid
                for interface in tracker_interfaces:
                    if interface not in self.available_interfaces:
                        errors["base"] = "invalid_interface"
                        return await self._show_setup_form(user_input, errors)

            return self.async_create_entry(title="OPNsense", data=user_input)

        except (APIException, requestsConnectionError):
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return await self._show_setup_form(user_input, errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            data = {
                CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, False),
                CONF_TRACKER_INTERFACES: user_input.get(CONF_TRACKER_INTERFACES, None),
            }
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=data,
            )

        available_interfaces = []
        if (
            OPNSENSE_DATA in self.hass.data
            and CONF_AVAILABLE_INTERFACES in self.hass.data[OPNSENSE_DATA]
        ):
            available_interfaces = self.hass.data[OPNSENSE_DATA][
                CONF_AVAILABLE_INTERFACES
            ]

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=reconfigure_entry.data.get(CONF_VERIFY_SSL, False),
                    ): bool,
                    vol.Optional(
                        CONF_TRACKER_INTERFACES,
                        default=reconfigure_entry.data.get(
                            CONF_TRACKER_INTERFACES, None
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=list(available_interfaces),
                            multiple=True,
                            sort=True,
                        )
                    ),
                }
            ),
        )

    async def async_step_import(
        self, import_data: (dict[str, Any])
    ) -> ConfigFlowResult:
        """Import a Yaml config."""
        self._async_abort_entries_match({CONF_URL: import_data[CONF_URL]})

        # Test connection
        api_data: APIData = {
            "api_key": import_data[CONF_API_KEY],
            "api_secret": import_data[CONF_API_SECRET],
            "base_url": import_data[CONF_URL],
            "verify_cert": import_data[CONF_VERIFY_SSL],
        }
        interfaces_client = diagnostics.InterfaceClient(**api_data)
        try:
            await self.hass.async_add_executor_job(interfaces_client.get_arp)
        except APIException:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="OPNsense", data=import_data)

    async def _async_check_connection(self, api_data: APIData) -> None:
        """Check connection to OPNsense."""
        interfaces_client = diagnostics.InterfaceClient(**api_data)
        await self.hass.async_add_executor_job(interfaces_client.get_arp)

    async def _async_get_available_interfaces(self, api_data: APIData) -> Interfaces:
        """Fetch available interfaces from OPNsense."""
        netinsight_client = diagnostics.NetworkInsightClient(**api_data)
        interface_details = await self.hass.async_add_executor_job(
            netinsight_client.get_interfaces
        )
        self.available_interfaces = interface_details.values()
        return self.available_interfaces
