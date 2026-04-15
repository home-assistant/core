"""Config flow for OPNsense."""

import logging
from typing import Any

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseClient,
    OPNsenseConnectionError,
    OPNsenseInvalidURL,
    OPNsenseSSLError,
    OPNsenseTimeoutError,
    OPNsenseUnknownFirmware,
)
from requests.exceptions import ConnectionError as requestsConnectionError
import voluptuous as vol

from homeassistant.components.version import async_get_clientsession
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACES, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_SECRET): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """OPNsense config flow."""

    def __init__(self) -> None:
        """Initialize OPNsense config flow."""
        self.available_interfaces: list[str] | None = None

    async def _show_setup_form(
        self,
        user_input: dict[Any, Any] | None = None,
        errors: dict[Any, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        description_placeholders = {
            "doc_url": "https://www.home-assistant.io/integrations/opnsense/"
        }

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
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

        verify_ssl = user_input[CONF_VERIFY_SSL]
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
        client = OPNsenseClient(
            user_input[CONF_URL],
            user_input[CONF_API_KEY],
            user_input[CONF_API_SECRET],
            session,
            opts={"verify_ssl": verify_ssl},
        )

        try:
            await self._async_check_connection(client)
            await self._async_get_available_interfaces(client)
            if tracker_interfaces and self.available_interfaces:
                # Verify that specified tracker interfaces are valid
                for interface in tracker_interfaces:
                    if interface not in self.available_interfaces:
                        errors["base"] = "invalid_interface"
                        return await self._show_setup_form(user_input, errors)

            return self.async_create_entry(title=user_input[CONF_URL], data=user_input)

        except OPNsenseInvalidURL:
            errors["base"] = "invalid_url"
        except OPNsenseSSLError:
            errors["base"] = "ssl_error"
        except OPNsenseConnectionError, OPNsenseTimeoutError, requestsConnectionError:
            errors["base"] = "cannot_connect"
        except OPNsenseUnknownFirmware:
            errors["base"] = "invalid_version"
        except OPNsenseBelowMinFirmware:
            errors["base"] = "invalid_version"
        except Exception:
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
                reconfigure_entry,
                data_updates=data,
            )
        session = async_get_clientsession(
            self.hass, verify_ssl=reconfigure_entry.data[CONF_VERIFY_SSL]
        )
        client = OPNsenseClient(
            reconfigure_entry.data[CONF_URL],
            reconfigure_entry.data[CONF_API_KEY],
            reconfigure_entry.data[CONF_API_SECRET],
            session,
            opts={"verify_ssl": reconfigure_entry.data[CONF_VERIFY_SSL]},
        )
        await self._async_get_available_interfaces(client)

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
                            options=list(self.available_interfaces or []),
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
        session = async_get_clientsession(
            self.hass, verify_ssl=import_data[CONF_VERIFY_SSL]
        )
        client = OPNsenseClient(
            import_data[CONF_URL],
            import_data[CONF_API_KEY],
            import_data[CONF_API_SECRET],
            session,
            opts={"verify_ssl": import_data[CONF_VERIFY_SSL]},
        )
        try:
            await client.validate()
        except OPNsenseInvalidURL:
            return self.async_abort(reason="invalid_url")
        except OPNsenseSSLError:
            return self.async_abort(reason="ssl_error")
        except OPNsenseConnectionError, OPNsenseTimeoutError, requestsConnectionError:
            return self.async_abort(reason="cannot_connect")
        except OPNsenseUnknownFirmware:
            return self.async_abort(reason="invalid_version")
        except OPNsenseBelowMinFirmware:
            return self.async_abort(reason="invalid_version")
        except Exception:  # Allowed in config flows
            _LOGGER.exception("Unexpected exception during import")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(title=import_data[CONF_URL], data=import_data)

    async def _async_check_connection(self, client: OPNsenseClient) -> None:
        """Check connection to OPNsense."""
        await client.validate()

    async def _async_get_available_interfaces(self, client: OPNsenseClient) -> None:
        """Fetch available interfaces from OPNsense."""
        try:
            interfaces_resp = await client.get_interfaces()
            self.available_interfaces = list(interfaces_resp.values())
        except Exception:
            _LOGGER.exception("Failed to fetch available interfaces")
            self.available_interfaces = []
