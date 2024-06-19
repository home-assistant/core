"""Config flow for Philips TV integration."""

from __future__ import annotations

from collections.abc import Mapping
import platform
from typing import Any

from haphilipsjs import ConnectionFailure, PairingFailure, PhilipsTV
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from . import LOGGER
from .const import CONF_ALLOW_NOTIFY, CONF_SYSTEM, CONST_APP_ID, CONST_APP_NAME, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST,
        ): str,
        vol.Required(
            CONF_API_VERSION,
            default=1,
        ): vol.In([1, 5, 6]),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ALLOW_NOTIFY, default=False): selector.BooleanSelector(),
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


async def _validate_input(
    hass: HomeAssistant, host: str, api_version: int
) -> PhilipsTV:
    """Validate the user input allows us to connect."""
    hub = PhilipsTV(host, api_version)

    await hub.getSystem()
    await hub.setTransport(hub.secured_transport)

    if not hub.system:
        raise ConnectionFailure("System data is empty")

    return hub


class PhilipsJSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Philips TV."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        super().__init__()
        self._current: dict[str, Any] = {}
        self._hub: PhilipsTV | None = None
        self._pair_state: Any = None
        self._entry: ConfigEntry | None = None

    async def _async_create_current(self) -> ConfigFlowResult:
        system = self._current[CONF_SYSTEM]
        if self._entry:
            self.hass.config_entries.async_update_entry(
                self._entry, data=self._entry.data | self._current
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=f"{system['name']} ({system['serialnumber']})",
            data=self._current,
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to pair with device."""
        assert self._hub

        errors: dict[str, str] = {}
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._current[CONF_HOST] = entry_data[CONF_HOST]
        self._current[CONF_API_VERSION] = entry_data[CONF_API_VERSION]
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input:
            self._current = user_input
            try:
                hub = await _validate_input(
                    self.hass, user_input[CONF_HOST], user_input[CONF_API_VERSION]
                )
            except ConnectionFailure as exc:
                LOGGER.error(exc)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if serialnumber := hub.system.get("serialnumber"):
                    await self.async_set_unique_id(serialnumber)
                    if self._entry is None:
                        self._abort_if_unique_id_configured()

                self._current[CONF_SYSTEM] = hub.system
                self._current[CONF_API_VERSION] = hub.api_version
                self._hub = hub

                if hub.pairing_type == "digest_auth_pairing":
                    return await self.async_step_pair()
                return await self._async_create_current()

        schema = self.add_suggested_values_to_schema(USER_SCHEMA, self._current)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
