"""Config flow for HomeWizard Energy."""

from aiohwenergy.hwenergy import SUPPORTED_DEVICES

import voluptuous as vol
from voluptuous import All, Length, Required, Schema
from voluptuous.util import Lower

from homeassistant.helpers.typing import ConfigType
from typing import Any, Dict, Optional
from homeassistant import config_entries
from aiohwenergy import HomeWizardEnergy

from .const import DOMAIN, LOGGER
from .helpers import async_validate_connection

from homeassistant.const import CONF_IP_ADDRESS


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomeWizard Energy."""

    VERSION = 1

    def __init__(self):
        """Set up setup flow."""
        pass

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        # Make connection with device
        api = HomeWizardEnergy(user_input[CONF_IP_ADDRESS])

        if not await async_validate_connection(api):
            return self.async_abort(reason="manual_config_request_error")

        # Validate metadata
        if api.device.api_version != "v1":
            return self.async_abort(reason="manual_config_unsupported_api_version")

        # Configure device
        entry_info = {
            "host": user_input[CONF_IP_ADDRESS],
            "port": 80,
            "api_enabled": "1",
            "path": "/api/v1",
            "product_name": api.device.product_name,
            "product_type": api.device.product_type,
            "serial": api.device.serial,
        }

        LOGGER.debug(entry_info)

        return await self.async_step_check(entry_info)

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""

        entry_info = {
            "host": discovery_info["host"],
            "port": discovery_info["port"],
            "api_enabled": (
                discovery_info["properties"]["api_enabled"]
                if "api_enabled" in discovery_info["properties"]
                else None
            ),
            "path": (
                discovery_info["properties"]["path"]
                if "path" in discovery_info["properties"]
                else None
            ),
            "product_name": (
                discovery_info["properties"]["product_name"]
                if "product_name" in discovery_info["properties"]
                else None
            ),
            "product_type": (
                discovery_info["properties"]["product_type"]
                if "product_type" in discovery_info["properties"]
                else None
            ),
            "serial": (
                discovery_info["properties"]["serial"]
                if "serial" in discovery_info["properties"]
                else None
            ),
        }

        return await self.async_step_check(entry_info)

    async def async_step_check(self, entry_info):
        """Perform some checks and create entry if OK."""

        LOGGER.debug("config_flow async_step_check")

        if entry_info["product_type"] not in SUPPORTED_DEVICES:
            LOGGER.warning(
                "Device (%s) not supported by integration" % entry_info["product_type"]
            )

        if entry_info["api_enabled"] != "1":
            LOGGER.warning("API must be enabled in the HomeWizard Energy App")
            return self.async_abort(reason="api_not_enabled")

        LOGGER.debug(f"entry_info: {entry_info}")

        if (
            ("host" not in entry_info)
            or ("port" not in entry_info)
            or ("serial" not in entry_info)
            or ("product_name" not in entry_info)
            or ("product_type" not in entry_info)
            or ("path" not in entry_info)
            or ("api_enabled" not in entry_info)
        ):
            LOGGER.warning("Invalid discovery parameters")
            return self.async_abort(reason="invalid_discovery_parameters")

        self.context["host"] = entry_info["host"]
        self.context["unique_id"] = "%s_%s" % (
            entry_info["product_type"],
            entry_info["serial"],
        )
        self.context["serial"] = entry_info["serial"]
        self.context["port"] = entry_info["port"]
        self.context["path"] = entry_info["path"]
        self.context["product_name"] = entry_info["product_name"]
        self.context["product_type"] = entry_info["product_type"]
        self.context["api_enabled"] = entry_info["api_enabled"]

        self.context["name"] = "%s (%s)" % (
            self.context["product_name"],
            self.context["serial"][-6:],
        )

        await self.async_set_unique_id(self.context["unique_id"])
        self._abort_if_unique_id_configured(updates=entry_info)

        self.context["title_placeholders"] = {
            "name": self.context["name"],
            "unique_id": self.context["unique_id"],
        }

        # TODO Check if device is already configured (but maybe moved to new IP)

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""

        LOGGER.debug("config_flow async_step_discovery_confirm")

        errors = {}

        schema = Schema(
            {
                Required("name", default=self.context["product_name"]): All(
                    str, Length(min=1)
                )
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={"name": self.context["product_name"]},
                data_schema=schema,
                errors=errors,
            )
        else:

            if self.context["api_enabled"] != "1":
                LOGGER.warning("API not enabled")
                return self.async_abort(reason="api_not_enabled")

            LOGGER.debug("async_step_discovery_confirm _create_entry")
            self.context["custom_name"] = (
                user_input["name"] if user_input["name"] != "" else self.context["name"]
            )
            if Lower(self.context["product_name"]) != Lower(user_input["name"]):
                title = "%s (%s)" % (
                    self.context["product_name"],
                    self.context["custom_name"],
                )
            else:
                title = self.context["custom_name"]

            return self.async_create_entry(
                title=title,
                data=self.context,
            )
