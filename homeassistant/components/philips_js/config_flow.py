"""Config flow for Philips TV integration."""
from __future__ import annotations

import platform
from typing import Any

from haphilipsjs import ConnectionFailure, PairingFailure, PhilipsTV
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_USERNAME,
)

from . import LOGGER
from .const import CONF_ALLOW_NOTIFY, CONF_SYSTEM, CONST_APP_ID, CONST_APP_NAME, DOMAIN


async def validate_input(
    hass: core.HomeAssistant, host: str, api_version: int
) -> tuple[dict, PhilipsTV]:
    """Validate the user input allows us to connect."""
    hub = PhilipsTV(host, api_version)

    await hub.getSystem()
    await hub.setTransport(hub.secured_transport)

    if not hub.system:
        raise ConnectionFailure("System data is empty")

    return hub


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Philips TV."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        super().__init__()
        self._current = {}
        self._hub: PhilipsTV | None = None
        self._pair_state: Any = None

    async def async_step_import(self, conf: dict) -> dict:
        """Import a configuration from config.yaml."""
        self._async_abort_entries_match({CONF_HOST: conf[CONF_HOST]})

        return await self.async_step_user(
            {
                CONF_HOST: conf[CONF_HOST],
                CONF_API_VERSION: conf[CONF_API_VERSION],
            }
        )

    async def _async_create_current(self):

        system = self._current[CONF_SYSTEM]
        return self.async_create_entry(
            title=f"{system['name']} ({system['serialnumber']})",
            data=self._current,
        )

    async def async_step_pair(self, user_input: dict | None = None) -> dict:
        """Attempt to pair with device."""
        assert self._hub

        errors = {}
        schema = vol.Schema(
            {
                vol.Required(CONF_PIN): str,
            }
        )

        if not user_input:
            try:
                self._pair_state = await self._hub.pairRequest(
                    CONST_APP_ID,
                    CONST_APP_NAME,
                    platform.node(),
                    platform.system(),
                    "native",
                )
            except PairingFailure as exc:
                LOGGER.debug(exc)
                return self.async_abort(
                    reason="pairing_failure",
                    description_placeholders={"error_id": exc.data.get("error_id")},
                )
            return self.async_show_form(
                step_id="pair", data_schema=schema, errors=errors
            )

        try:
            username, password = await self._hub.pairGrant(
                self._pair_state, user_input[CONF_PIN]
            )
        except PairingFailure as exc:
            LOGGER.debug(exc)
            if exc.data.get("error_id") == "INVALID_PIN":
                errors[CONF_PIN] = "invalid_pin"
                return self.async_show_form(
                    step_id="pair", data_schema=schema, errors=errors
                )

            return self.async_abort(
                reason="pairing_failure",
                description_placeholders={"error_id": exc.data.get("error_id")},
            )

        self._current[CONF_USERNAME] = username
        self._current[CONF_PASSWORD] = password
        return await self._async_create_current()

    async def async_step_user(self, user_input: dict | None = None) -> dict:
        """Handle the initial step."""
        errors = {}
        if user_input:
            self._current = user_input
            try:
                hub = await validate_input(
                    self.hass, user_input[CONF_HOST], user_input[CONF_API_VERSION]
                )
            except ConnectionFailure as exc:
                LOGGER.error(exc)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:

                await self.async_set_unique_id(hub.system["serialnumber"])
                self._abort_if_unique_id_configured()

                self._current[CONF_SYSTEM] = hub.system
                self._current[CONF_API_VERSION] = hub.api_version
                self._hub = hub

                if hub.pairing_type == "digest_auth_pairing":
                    return await self.async_step_pair()
                return await self._async_create_current()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._current.get(CONF_HOST)): str,
                vol.Required(
                    CONF_API_VERSION, default=self._current.get(CONF_API_VERSION, 1)
                ): vol.In([1, 5, 6]),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @core.callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for AEMET."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ALLOW_NOTIFY,
                    default=self.config_entry.options.get(CONF_ALLOW_NOTIFY),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
