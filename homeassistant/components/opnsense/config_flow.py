"""Config flow for OPNsense."""

import logging
from typing import Any

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
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

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


def tracker_interfaces_schema(
    interfaces: list[str], selected: list[str] | None = None
) -> vol.Schema:
    """Schema to display available interfaces for device tracking selection."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_TRACKER_INTERFACES,
                default=selected or [],
            ): cv.multi_select(interfaces),
        }
    )


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """OPNsense config flow."""

    def __init__(self) -> None:
        """Initialize OPNsense config flow."""
        self.available_interfaces: list[str] | None = None
        self._step_user_input: dict[str, Any] | None = None

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
        user_input: dict[Any, Any] | None = None,
        errors: dict[Any, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the tracker interfaces selection form to the user."""
        if user_input is None:
            user_input = {}

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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user step: credentials and connection test."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form(user_input, None)

        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

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
            errors["base"] = "invalid_version"
        except OPNsenseBelowMinFirmware:
            errors["base"] = "invalid_version"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Save credentials for next step
            self._step_user_input = user_input
            return await self.async_step_interfaces()

        return await self._show_setup_form(user_input, errors)

    async def async_step_interfaces(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle tracker interface selection step."""
        if user_input is None:
            return await self._show_interfaces_form(user_input, None)

        # Compose entry data from credentials and selected interfaces
        step_user_input = getattr(self, "_step_user_input", None)
        if not isinstance(step_user_input, dict) or CONF_URL not in step_user_input:
            return await self.async_step_user()

        entry_data: dict[str, Any] = dict(step_user_input)
        if user_input.get(CONF_TRACKER_INTERFACES):
            entry_data[CONF_TRACKER_INTERFACES] = user_input[CONF_TRACKER_INTERFACES]
        return self.async_create_entry(title=entry_data[CONF_URL], data=entry_data)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
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
            interfaces_resp = await client.get_interfaces()
        except OPNsenseInvalidURL:
            return self.async_abort(reason="invalid_url")
        except OPNsenseInvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except OPNsensePrivilegeMissing:
            return self.async_abort(reason="privilege_missing")
        except OPNsenseSSLError:
            return self.async_abort(reason="ssl_error")
        except OPNsenseConnectionError, OPNsenseTimeoutError:
            return self.async_abort(reason="cannot_connect")
        except OPNsenseUnknownFirmware:
            return self.async_abort(reason="invalid_version")
        except OPNsenseBelowMinFirmware:
            return self.async_abort(reason="invalid_version")
        except Exception:  # Allowed in config flows
            _LOGGER.exception("Unexpected exception during import")
            return self.async_abort(reason="unknown")

        # Validate CONF_TRACKER_INTERFACES if present and not empty
        data = dict(import_data)
        if CONF_TRACKER_INTERFACES in data:
            if not data[CONF_TRACKER_INTERFACES]:
                data.pop(CONF_TRACKER_INTERFACES)
            else:
                known_interfaces = [
                    name
                    for ifinfo in interfaces_resp.values()
                    if (name := ifinfo.get("name"))
                ]
                self.available_interfaces = list(known_interfaces)
                # Abort import if any specified tracker interface is not found
                missing = [
                    intf_description
                    for intf_description in data[CONF_TRACKER_INTERFACES]
                    if intf_description not in known_interfaces
                ]
                if missing:
                    # Create a repair to guide the user
                    async_create_issue(
                        self.hass,
                        DOMAIN,
                        f"import_failed_missing_interfaces_{data[CONF_URL]}",
                        is_fixable=False,
                        severity=IssueSeverity.CRITICAL,
                        translation_key="import_failed_missing_interfaces",
                        translation_placeholders={
                            "url": data[CONF_URL],
                            "missing": ", ".join(missing),
                            "found": ", ".join(known_interfaces),
                        },
                    )
                    return self.async_abort(reason="import_failed_missing_interfaces")

                async_delete_issue(
                    self.hass,
                    DOMAIN,
                    f"import_failed_missing_interfaces_{data[CONF_URL]}",
                )
        return self.async_create_entry(title=import_data[CONF_URL], data=data)

    async def _async_check_connection(self, client: OPNsenseClient) -> None:
        """Check connection to OPNsense."""
        await client.validate()
