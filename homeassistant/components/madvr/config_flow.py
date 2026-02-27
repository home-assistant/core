"""Config flow for madVR Envy integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from madvr_envy import MadvrEnvyClient
from madvr_envy import exceptions as envy_exceptions

from .const import (
    DEFAULT_COMMAND_TIMEOUT,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_ENABLE_ADVANCED_ENTITIES,
    DEFAULT_PORT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_RECONNECT_INITIAL_BACKOFF,
    DEFAULT_RECONNECT_JITTER,
    DEFAULT_RECONNECT_MAX_BACKOFF,
    DEFAULT_SYNC_TIMEOUT,
    DOMAIN,
    NAME,
    OPT_COMMAND_TIMEOUT,
    OPT_CONNECT_TIMEOUT,
    OPT_ENABLE_ADVANCED_ENTITIES,
    OPT_READ_TIMEOUT,
    OPT_RECONNECT_INITIAL_BACKOFF,
    OPT_RECONNECT_JITTER,
    OPT_RECONNECT_MAX_BACKOFF,
    OPT_SYNC_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
)


class MadvrEnvyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for madVR Envy."""

    VERSION = 1
    _reauth_entry: ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])

            unique_id, mac_address = await _validate_connection(host, port)
            if unique_id is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
                title = f"{NAME} ({mac_address})" if mac_address else f"{NAME} ({host})"
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauth flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm(entry_data)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])

            unique_id, _ = await _validate_connection(host, port)
            if unique_id is None:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, CONF_HOST: host, CONF_PORT: port},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self._reauth_entry.data.get(CONF_HOST, "")
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=self._reauth_entry.data.get(CONF_PORT, DEFAULT_PORT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MadvrEnvyOptionsFlowHandler(config_entry)


class MadvrEnvyOptionsFlowHandler(OptionsFlow):
    """Handle madVR Envy options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            initial_backoff = float(user_input[OPT_RECONNECT_INITIAL_BACKOFF])
            max_backoff = float(user_input[OPT_RECONNECT_MAX_BACKOFF])
            jitter = float(user_input[OPT_RECONNECT_JITTER])
            if initial_backoff > max_backoff:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_build_options_schema(self._config_entry),
                    errors={"base": "invalid_backoff"},
                )
            if jitter < 0.0 or jitter > 1.0:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_build_options_schema(self._config_entry),
                    errors={"base": "invalid_jitter"},
                )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(self._config_entry),
        )


async def _validate_connection(host: str, port: int) -> tuple[str | None, str | None]:
    client = MadvrEnvyClient(host=host, port=port)
    try:
        await client.start()
        await client.wait_synced(timeout=DEFAULT_SYNC_TIMEOUT)
    except (
        envy_exceptions.ConnectionFailedError,
        envy_exceptions.ConnectionTimeoutError,
        envy_exceptions.NotConnectedError,
        TimeoutError,
    ):
        return None, None
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error during madVR Envy connection validation")
        return None, None
    finally:
        await client.stop()

    mac_address = client.state.mac_address
    if mac_address:
        normalized_mac = mac_address.lower().replace(":", "")
        return f"{DOMAIN}_{normalized_mac}", mac_address

    return f"{DOMAIN}_{host}_{port}", None


def _build_options_schema(config_entry: ConfigEntry) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                OPT_SYNC_TIMEOUT,
                default=config_entry.options.get(OPT_SYNC_TIMEOUT, DEFAULT_SYNC_TIMEOUT),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(
                OPT_CONNECT_TIMEOUT,
                default=config_entry.options.get(OPT_CONNECT_TIMEOUT, DEFAULT_CONNECT_TIMEOUT),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(
                OPT_COMMAND_TIMEOUT,
                default=config_entry.options.get(OPT_COMMAND_TIMEOUT, DEFAULT_COMMAND_TIMEOUT),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(
                OPT_READ_TIMEOUT,
                default=config_entry.options.get(OPT_READ_TIMEOUT, DEFAULT_READ_TIMEOUT),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(
                OPT_RECONNECT_INITIAL_BACKOFF,
                default=config_entry.options.get(
                    OPT_RECONNECT_INITIAL_BACKOFF,
                    DEFAULT_RECONNECT_INITIAL_BACKOFF,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0)),
            vol.Required(
                OPT_RECONNECT_MAX_BACKOFF,
                default=config_entry.options.get(
                    OPT_RECONNECT_MAX_BACKOFF,
                    DEFAULT_RECONNECT_MAX_BACKOFF,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0)),
            vol.Required(
                OPT_RECONNECT_JITTER,
                default=config_entry.options.get(
                    OPT_RECONNECT_JITTER,
                    DEFAULT_RECONNECT_JITTER,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Required(
                OPT_ENABLE_ADVANCED_ENTITIES,
                default=config_entry.options.get(
                    OPT_ENABLE_ADVANCED_ENTITIES,
                    DEFAULT_ENABLE_ADVANCED_ENTITIES,
                ),
            ): bool,
        }
    )
