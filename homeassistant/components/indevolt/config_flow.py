"""Config flow for Indevolt integration."""

import logging
from typing import Any

from aiohttp import ClientError
from indevolt_api import IndevoltAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_GENERATION, CONF_SERIAL_NUMBER, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IndevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for Indevolt integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovered_host: str | None = None
        self._discovered_device_data: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user configuration step."""
        errors: dict[str, str] = {}

        # Attempt to setup from user input
        if user_input is not None:
            errors, device_data = await self._async_validate_input(user_input)

            if not errors and device_data:
                await self.async_set_unique_id(device_data[CONF_SERIAL_NUMBER])

                # Handle initial setup
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"INDEVOLT {device_data[CONF_MODEL]}",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        **device_data,
                    },
                )

        # Retrieve user input
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the Indevolt device host."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        # Attempt to setup from user input
        if user_input is not None:
            errors, device_data = await self._async_validate_input(user_input)

            if not errors and device_data:
                await self.async_set_unique_id(device_data[CONF_SERIAL_NUMBER])
                self._abort_if_unique_id_mismatch(reason="different_device")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        **device_data,
                    },
                )

        # Retrieve user input (prefilled form)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_HOST): str}),
                reconfigure_entry.data,
            ),
            errors=errors,
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle UDP broadcast discovery."""
        host = discovery_info["host"]

        try:
            device_data = await self._async_get_device_data(host)

        except TimeoutError, ConnectionError, ClientError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(device_data[CONF_SERIAL_NUMBER])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.context["title_placeholders"] = {"name": device_data[CONF_MODEL]}
        self._discovered_host = host
        self._discovered_device_data = device_data

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm UDP discovery by user."""
        assert self._discovered_host is not None
        assert self._discovered_device_data is not None

        # Attempt to setup from user input
        if user_input is not None:
            return self.async_create_entry(
                title=f"INDEVOLT {self._discovered_device_data[CONF_MODEL]}",
                data={
                    CONF_HOST: self._discovered_host,
                    **self._discovered_device_data,
                },
            )

        # Retrieve user confirmation
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                CONF_HOST: self._discovered_host,
                CONF_MODEL: self._discovered_device_data[CONF_MODEL],
            },
        )

    async def _async_validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Validate user input and return errors dict and device data."""
        errors = {}
        device_data = None

        try:
            device_data = await self._async_get_device_data(user_input[CONF_HOST])
        except TimeoutError:
            errors["base"] = "timeout"
        except ConnectionError, ClientError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unknown error occurred while verifying device")
            errors["base"] = "unknown"

        return errors, device_data

    async def _async_get_device_data(self, host: str) -> dict[str, Any]:
        """Get device data (type, serial number, generation) from API."""
        api = IndevoltAPI(host, DEFAULT_PORT, async_get_clientsession(self.hass))
        config_data = await api.get_config()
        device_data = config_data["device"]

        return {
            CONF_SERIAL_NUMBER: device_data["sn"],
            CONF_GENERATION: device_data["generation"],
            CONF_MODEL: device_data["type"],
        }
