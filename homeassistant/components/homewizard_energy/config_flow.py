"""Config flow for Homewizard Energy."""
from __future__ import annotations

import logging
from typing import Any

import aiohwenergy
from aiohwenergy.hwenergy import SUPPORTED_DEVICES
import async_timeout
from voluptuous import Required, Schema

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow, FlowResult

from .const import CONF_PRODUCT_NAME, CONF_PRODUCT_TYPE, CONF_SERIAL, DOMAIN

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

        device_info = await self._async_try_connect_and_fetch(
            user_input[CONF_IP_ADDRESS]
        )

        entry_info = {
            CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
            CONF_PORT: 80,
            CONF_PRODUCT_TYPE: device_info[CONF_PRODUCT_TYPE],
            CONF_PRODUCT_NAME: device_info[CONF_PRODUCT_NAME],
            CONF_SERIAL: device_info[CONF_SERIAL],
        }

        # Add entry
        return await self._async_create_entry(entry_info)

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

        device_info = await self._async_try_connect_and_fetch(discovery_info["host"])

        # Pass parameters
        self.context["entry_info"] = {
            CONF_IP_ADDRESS: discovery_info["host"],
            CONF_PORT: discovery_info["port"],
            CONF_PRODUCT_TYPE: device_info[CONF_PRODUCT_TYPE],
            CONF_PRODUCT_NAME: device_info[CONF_PRODUCT_NAME],
            CONF_SERIAL: device_info[CONF_SERIAL],
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, entry_info: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if entry_info is not None:
            return await self._async_create_entry(self.context["entry_info"])

        self._set_confirm_only()

        placeholders = {
            CONF_PRODUCT_TYPE: self.context["entry_info"][CONF_PRODUCT_TYPE],
            CONF_SERIAL: self.context["entry_info"][CONF_SERIAL],
            CONF_IP_ADDRESS: self.context["entry_info"][CONF_IP_ADDRESS],
        }
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def _async_try_connect_and_fetch(self, ip_address: str) -> dict[str, Any]:
        """Try to connect."""
        # Make connection with device
        # This is to test the connection and to get info for unique_id
        energy_api = aiohwenergy.HomeWizardEnergy(ip_address)

        initialized = False
        try:
            with async_timeout.timeout(10):
                await energy_api.initialize()
                if energy_api.device is not None:
                    initialized = True

        except aiohwenergy.DisabledError as ex:
            _LOGGER.error("API disabled, API must be enabled in the app")
            raise AbortFlow("api_not_enabled") from ex

        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(
                f"Error connecting with Energy Device at {ip_address}",
            )
            raise AbortFlow("unknown_error") from ex

        finally:
            await energy_api.close()

        if not initialized:
            _LOGGER.error("Initialization failed")
            raise AbortFlow("unknown_error")

        # Validate metadata
        if energy_api.device.api_version != "v1":
            raise AbortFlow("unsupported_api_version")

        if energy_api.device.product_type not in SUPPORTED_DEVICES:
            _LOGGER.error(
                "Device (%s) not supported by integration",
                energy_api.device.product_type,
            )
            raise AbortFlow("device_not_supported")

        return {
            CONF_PRODUCT_NAME: energy_api.device.product_name,
            CONF_PRODUCT_TYPE: energy_api.device.product_type,
            CONF_SERIAL: energy_api.device.serial,
        }

    async def _async_create_entry(self, entry_info):
        """Validate uniqueness and add entry."""

        _LOGGER.debug("config_flow async_helper_check")
        await self.async_set_unique_id(
            f"{entry_info[CONF_PRODUCT_TYPE]}_{entry_info[CONF_PRODUCT_TYPE]}"
        )
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: entry_info[CONF_IP_ADDRESS]}
        )

        entry_info[
            CONF_NAME
        ] = f"{entry_info[CONF_PRODUCT_NAME]} ({entry_info[CONF_PRODUCT_TYPE]})"

        return self.async_create_entry(
            title=entry_info[CONF_NAME],
            data=entry_info,
        )
