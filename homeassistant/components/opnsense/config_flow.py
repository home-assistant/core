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
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
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
            if unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
            self._entry_data = dict(user_input)
            return await self.async_step_interfaces(user_input)

        return await self._show_setup_form({}, errors)

    async def async_step_interfaces(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle tracker interface selection step."""
        if CONF_TRACKER_INTERFACES not in user_input:
            return await self._show_interfaces_form(user_input, None)

        if user_input.get(CONF_TRACKER_INTERFACES):
            self._entry_data[CONF_TRACKER_INTERFACES] = user_input[
                CONF_TRACKER_INTERFACES
            ]

        return self.async_create_entry(
            title=self._entry_data[CONF_URL], data=self._entry_data
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a Yaml config."""
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
            return self._abort_import(reason="invalid_url", url=import_data[CONF_URL])
        except OPNsenseInvalidAuth:
            return self._abort_import(reason="invalid_auth", url=import_data[CONF_URL])
        except OPNsensePrivilegeMissing:
            return self._abort_import(
                reason="privilege_missing", url=import_data[CONF_URL]
            )
        except OPNsenseSSLError:
            return self._abort_import(reason="ssl_error", url=import_data[CONF_URL])
        except OPNsenseConnectionError, OPNsenseTimeoutError:
            return self._abort_import(
                reason="cannot_connect", url=import_data[CONF_URL]
            )
        except OPNsenseUnknownFirmware:
            return self._abort_import(
                reason="invalid_version", url=import_data[CONF_URL]
            )
        except OPNsenseBelowMinFirmware:
            return self._abort_import(
                reason="invalid_version", url=import_data[CONF_URL]
            )
        except Exception:  # Allowed in config flows
            _LOGGER.exception("Unexpected exception during import")
            return self._abort_import(reason="unknown", url=import_data[CONF_URL])

        unique_id = await client.get_device_unique_id()
        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

        # Validate CONF_TRACKER_INTERFACES if present and not empty
        verified_data = dict(import_data)
        if CONF_TRACKER_INTERFACES in verified_data:
            if not verified_data[CONF_TRACKER_INTERFACES]:
                verified_data.pop(CONF_TRACKER_INTERFACES)
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
                    for intf_description in verified_data[CONF_TRACKER_INTERFACES]
                    if intf_description not in known_interfaces
                ]
                if missing:
                    # Create a repair to guide the user
                    async_create_issue(
                        self.hass,
                        DOMAIN,
                        f"import_failed_missing_interfaces_{verified_data[CONF_URL]}",
                        is_fixable=False,
                        severity=IssueSeverity.CRITICAL,
                        translation_key="import_failed_missing_interfaces",
                        translation_placeholders={
                            "url": verified_data[CONF_URL],
                            "missing": ", ".join(missing),
                            "found": ", ".join(known_interfaces),
                            "integration_title": "OPNsense",
                        },
                    )
                    return self.async_abort(
                        reason="import_failed_missing_interfaces",
                        description_placeholders={
                            "url": verified_data[CONF_URL],
                            "missing": ", ".join(missing),
                            "found": ", ".join(known_interfaces),
                            "integration_title": "OPNsense",
                        },
                    )

        # Clear any previous import issues if interfaces are now valid
        async_delete_issue(
            self.hass,
            DOMAIN,
            f"import_failed_missing_interfaces_{verified_data[CONF_URL]}",
        )

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2026.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "OPNsense",
            },
        )
        return self.async_create_entry(
            title=verified_data[CONF_URL], data=verified_data
        )

    def _abort_import(self, reason: str, url: str) -> ConfigFlowResult:
        """Create an issue for import errors and abort the import."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"import_failed_{reason}_{url}",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key=f"import_failed_{reason}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "OPNsense",
            },
        )
        return self.async_abort(
            reason=reason,
            description_placeholders={
                "integration_title": "OPNsense",
            },
        )
