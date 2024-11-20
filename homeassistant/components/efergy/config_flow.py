"""Config flow for Efergy integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pyefergy import Efergy, exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DOMAIN, LOGGER


class EfergyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Efergy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]

            self._async_abort_entries_match({CONF_API_KEY: api_key})
            hid, error = await self._async_try_connect(api_key)
            if error is None:
                entry = await self.async_set_unique_id(hid)
                if entry:
                    return self.async_update_reload_and_abort(entry, data=user_input)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_API_KEY: api_key},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_user()

    async def _async_try_connect(self, api_key: str) -> tuple[str | None, str | None]:
        """Try connecting to Efergy servers."""
        api = Efergy(
            api_key,
            session=async_get_clientsession(self.hass),
            utc_offset=self.hass.config.time_zone,
        )
        try:
            await api.async_status()
        except exceptions.ConnectError:
            return None, "cannot_connect"
        except exceptions.InvalidAuth:
            return None, "invalid_auth"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return None, "unknown"
        return api.info["hid"], None
