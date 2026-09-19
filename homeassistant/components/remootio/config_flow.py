"""Config flow for the Remootio integration."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from pyremootio import (
    RemootioAuthenticationError,
    RemootioClient,
    RemootioConnectionError,
    RemootioCryptoError,
    RemootioTimeoutError,
)

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_API_AUTH_KEY, CONF_API_SECRET_KEY, DOMAIN, device_name

_LOGGER = logging.getLogger(__name__)

_PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_API_SECRET_KEY): _PASSWORD_SELECTOR,
        probatio.Required(CONF_API_AUTH_KEY): _PASSWORD_SELECTOR,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_API_SECRET_KEY): _PASSWORD_SELECTOR,
        probatio.Required(CONF_API_AUTH_KEY): _PASSWORD_SELECTOR,
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Optional(CONF_API_SECRET_KEY): _PASSWORD_SELECTOR,
        probatio.Optional(CONF_API_AUTH_KEY): _PASSWORD_SELECTOR,
    }
)


async def _async_get_serial(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Probe the device and return its serial. Always closes the websocket."""
    async with RemootioClient(
        data[CONF_HOST],
        data[CONF_API_SECRET_KEY],
        data[CONF_API_AUTH_KEY],
        async_get_clientsession(hass),
    ) as client:
        return client.serial_number


async def _async_validate_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str | None, dict[str, str]]:
    """Probe host and keys. Returns (serial, errors)."""
    errors: dict[str, str] = {}
    serial: str | None = None
    try:
        serial = await _async_get_serial(hass, data)
    except ValueError:
        errors["base"] = "invalid_auth"
    except RemootioAuthenticationError, RemootioCryptoError:
        errors["base"] = "invalid_auth"
    except RemootioConnectionError, RemootioTimeoutError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception while connecting to Remootio")
        errors["base"] = "unknown"
    else:
        if not serial:
            errors["base"] = "cannot_connect"
    return serial, errors


async def _async_pause_runtime(entry: ConfigEntry) -> RemootioClient | None:
    """Close the live websocket so a probe can authenticate."""
    if entry.state is not ConfigEntryState.LOADED:
        return None
    client: RemootioClient = entry.runtime_data
    await client.disconnect()
    return client


async def _async_resume_runtime(client: RemootioClient | None) -> None:
    """Reconnect the live client after a failed probe."""
    if client is None:
        return
    try:
        await client.connect(reconnect=True)
    except Exception:
        _LOGGER.exception("Failed to restore Remootio connection after a failed probe")


async def _async_validate_loaded_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: dict[str, Any],
) -> tuple[str | None, dict[str, str], RemootioClient | None]:
    """Pause the live session, probe, and resume if the probe failed."""
    runtime = await _async_pause_runtime(entry)
    try:
        serial, errors = await _async_validate_connection(hass, data)
    except asyncio.CancelledError:
        await _async_resume_runtime(runtime)
        raise
    if serial is None:
        await _async_resume_runtime(runtime)
        return None, errors, None
    return serial, errors, runtime


def _reconfigure_updates(user_input: dict[str, Any]) -> dict[str, Any]:
    """Host is required. Blank API keys keep the stored values."""
    updates = {CONF_HOST: user_input[CONF_HOST]}
    if secret := user_input.get(CONF_API_SECRET_KEY):
        updates[CONF_API_SECRET_KEY] = secret
    if auth := user_input.get(CONF_API_AUTH_KEY):
        updates[CONF_API_AUTH_KEY] = auth
    return updates


class RemootioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remootio."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user entering host and API keys."""
        errors: dict[str, str] = {}
        if user_input is not None:
            serial, errors = await _async_validate_connection(self.hass, user_input)
            if serial is not None:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_name(serial), data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored API keys are no longer valid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for new API keys. Host stays on the existing entry."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            serial, errors, runtime = await _async_validate_loaded_entry(
                self.hass, reauth_entry, {**reauth_entry.data, **user_input}
            )
            if serial is not None:
                return await self._async_finish_probe(
                    reauth_entry, runtime, user_input, serial
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user change host or API keys without removing the device."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            updates = _reconfigure_updates(user_input)
            serial, errors, runtime = await _async_validate_loaded_entry(
                self.hass, reconfigure_entry, {**reconfigure_entry.data, **updates}
            )
            if serial is not None:
                return await self._async_finish_probe(
                    reconfigure_entry, runtime, updates, serial
                )

        suggested = (
            user_input
            if user_input is not None
            else {CONF_HOST: reconfigure_entry.data[CONF_HOST]}
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA, suggested
            ),
            errors=errors,
        )

    async def _async_finish_probe(
        self,
        entry: ConfigEntry,
        runtime: RemootioClient | None,
        data_updates: dict[str, Any],
        serial: str,
    ) -> ConfigFlowResult:
        """Abort on serial mismatch after restore, or reload with the new data."""
        await self.async_set_unique_id(serial)
        try:
            self._abort_if_unique_id_mismatch()
        except AbortFlow:
            await _async_resume_runtime(runtime)
            raise
        reason = (
            "reconfigure_successful"
            if self.source == SOURCE_RECONFIGURE
            else "reauth_successful"
        )
        return self.async_update_reload_and_abort(
            entry, data_updates=data_updates, reason=reason
        )
