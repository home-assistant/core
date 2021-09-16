"""Config flow for Homewizard Energy."""
from __future__ import annotations

import logging
from typing import Any

import aiohwenergy
from aiohwenergy.hwenergy import SUPPORTED_DEVICES
import async_timeout
from voluptuous import All, Length, Required, Schema
from voluptuous.util import Lower

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for P1 meter."""

    VERSION = 1

    def __init__(self):
        """Set up the instance."""
        _LOGGER.debug("config_flow __init__")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        _LOGGER.debug("config_flow async_step_user")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=Schema(
                    {
                        Required(CONF_IP_ADDRESS): str,
                    }
                ),
                errors=None,
            )

        entry_info = {
            CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
            CONF_PORT: 80,
        }

        return await self.async_step_check(entry_info)

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""

        _LOGGER.debug("config_flow async_step_zeroconf")

        # Validate doscovery entry
        if (
            "host" not in discovery_info
            or "api_enabled" not in discovery_info["properties"]
            or "path" not in discovery_info["properties"]
            or "product_name" not in discovery_info["properties"]
            or "product_type" not in discovery_info["properties"]
            or "serial" not in discovery_info["properties"]
        ):
            return self.async_abort(reason="invalid_discovery_parameters")

        if (discovery_info["properties"]["path"]) != "/api/v1":
            return self.async_abort(reason="unsupported_api_version")

        if (discovery_info["properties"]["api_enabled"]) != "1":
            return self.async_abort(reason="api_not_enabled")

        # Pass parameters
        entry_info = {
            CONF_IP_ADDRESS: discovery_info["host"],
            CONF_PORT: discovery_info["port"],
        }

        return await self.async_step_check(entry_info)

    async def async_step_check(self, entry_info):
        """Validate API connection and fetch metadata."""

        _LOGGER.debug("config_flow async_step_check")

        # Make connection with device
        energy_api = aiohwenergy.HomeWizardEnergy(entry_info[CONF_IP_ADDRESS])

        initialized = False
        try:
            with async_timeout.timeout(10):
                await energy_api.initialize()
                if energy_api.device is not None:
                    initialized = True

        except aiohwenergy.DisabledError:
            _LOGGER.error("API disabled, API must be enabled in the app")
            return self.async_abort(reason="api_not_enabled")

        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(
                "Error connecting with Energy Device at %s",
                entry_info[CONF_IP_ADDRESS],
            )
            return self.async_abort(reason="unknown_error")

        finally:
            await energy_api.close()

        if not initialized:
            _LOGGER.error("Initialization failed")
            return self.async_abort(reason="unknown_error")

        # Validate metadata
        if energy_api.device.api_version != "v1":
            return self.async_abort(reason="unsupported_api_version")

        if energy_api.device.product_type not in SUPPORTED_DEVICES:
            _LOGGER.error(
                "Device (%s) not supported by integration",
                energy_api.device.product_type,
            )
            return self.async_abort(reason="device_not_supported")

        # Configure device
        entry_info["product_name"] = energy_api.device.product_name
        entry_info["product_type"] = energy_api.device.product_type
        entry_info["serial"] = energy_api.device.serial

        self.context[CONF_HOST] = entry_info[CONF_IP_ADDRESS]
        self.context[CONF_PORT] = entry_info[CONF_PORT]
        self.context["product_name"] = entry_info["product_name"]
        self.context["product_type"] = entry_info["product_type"]
        self.context["serial"] = entry_info["serial"]
        self.context[
            "unique_id"
        ] = f"{entry_info['product_type']}_{entry_info['serial']}"
        self.context[
            "name"
        ] = f"{self.context['product_name']} ({self.context['serial'][-6:]})"

        await self.async_set_unique_id(self.context["unique_id"])
        self._abort_if_unique_id_configured(updates=entry_info)

        self.context["title_placeholders"] = {
            "name": self.context["name"],
            "unique_id": self.context["unique_id"],
        }

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of node."""

        _LOGGER.debug("config_flow async_step_confirm")

        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={"name": self.context["product_name"]},
                data_schema=Schema(
                    {
                        Required("name", default=self.context["product_name"]): All(
                            str, Length(min=1)
                        )
                    }
                ),
                errors=None,
            )

        # Format name
        self.context["custom_name"] = user_input["name"]
        if Lower(self.context["product_name"]) != Lower(user_input["name"]):
            title = f"{self.context['product_name']} ({self.context['custom_name']})"
        else:
            title = self.context["custom_name"]

        # Finish up
        return self.async_create_entry(
            title=title,
            data=self.context,
        )
