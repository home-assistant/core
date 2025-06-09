"""Config flow for the Uptime Kuma integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pyuptimekuma import (
    UptimeKuma,
    UptimeKumaAuthenticationException,
    UptimeKumaException,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="url",
            ),
        ),
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Optional(CONF_API_KEY): str,
    }
)


class UptimeKumaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Uptime Kuma."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            url = URL(user_input[CONF_URL])
            if url.path.endswith("/"):
                url = url.with_path(url.path[:-1])
            self._async_abort_entries_match({CONF_URL: url.human_repr()})

            uptime_kuma = UptimeKuma(
                session,
                str(url),
                "",
                user_input[CONF_API_KEY],
                user_input[CONF_VERIFY_SSL],
            )

            try:
                await uptime_kuma.async_get_monitors()
            except UptimeKumaAuthenticationException:
                errors["base"] = "invalid_auth"
            except UptimeKumaException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if TYPE_CHECKING:
                    assert url.host
                return self.async_create_entry(
                    title=url.host,
                    data={**user_input, CONF_URL: url.human_repr()},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )
