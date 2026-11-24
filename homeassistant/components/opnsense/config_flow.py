"""Config flow for OPNsense."""

import logging
from typing import Any, override

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseClient,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseSSLError,
    OPNsenseTimeoutError,
    OPNsenseUnknownFirmware,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACES, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): str,
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
        probatio.Required(probatio.Secret(CONF_API_SECRET)): str,
        probatio.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


def tracker_interfaces_schema(
    interfaces: list[str], selected: list[str] | None = None
) -> probatio.Schema:
    """Schema to display available interfaces for device tracking selection."""
    return probatio.Schema(
        {
            probatio.Optional(
                CONF_TRACKER_INTERFACES,
                default=selected or [],
            ): SelectSelector(
                SelectSelectorConfig(
                    options=interfaces, mode=SelectSelectorMode.DROPDOWN, multiple=True
                )
            ),
        }
    )


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """OPNsense config flow."""

    def __init__(self) -> None:
        """Initialize OPNsense config flow."""
        self.available_interfaces: list[str] | None = None
        self._entry_data: dict[str, Any] = {}

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

    async def _show_interfaces_form(
        self,
        user_input: dict[Any, Any],
        errors: dict[Any, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the tracker interfaces selection form to the user."""
        return self.async_show_form(
            step_id="interfaces",
            data_schema=self.add_suggested_values_to_schema(
                tracker_interfaces_schema(
                    self.available_interfaces or [],
                    user_input.get(CONF_TRACKER_INTERFACES),
                ),
                user_input,
            ),
            errors=errors or {},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user step: credentials and connection test."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form(user_input, None)

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
            await client.validate()
            interfaces_resp = await client.get_interfaces()
            known_interfaces = [
                name
                for ifinfo in interfaces_resp.values()
                if (name := ifinfo.get("name"))
            ]
            self.available_interfaces = list(known_interfaces)
        except OPNsenseInvalidAuth:
            errors["base"] = "invalid_auth"
        except OPNsensePrivilegeMissing:
            errors["base"] = "privilege_missing"
        except OPNsenseInvalidURL:
            errors["base"] = "invalid_url"
        except OPNsenseSSLError:
            errors["base"] = "ssl_error"
        except OPNsenseConnectionError, OPNsenseTimeoutError:
            errors["base"] = "cannot_connect"
        except OPNsenseUnknownFirmware:
            errors["base"] = "unknown_version"
        except OPNsenseBelowMinFirmware:
            errors["base"] = "invalid_version"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            unique_id = await client.get_device_unique_id()
            if not unique_id:
                return self.async_abort(reason="no_unique_id")
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            self._entry_data = user_input
            return await self.async_step_interfaces()

        return await self._show_setup_form(user_input, errors)

    async def async_step_interfaces(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle tracker interface selection step."""
        if user_input is None:
            return await self._show_interfaces_form({}, None)

        if user_input.get(CONF_TRACKER_INTERFACES):
            self._entry_data[CONF_TRACKER_INTERFACES] = user_input[
                CONF_TRACKER_INTERFACES
            ]

        return self.async_create_entry(
            title=self._entry_data[CONF_URL], data=self._entry_data
        )
