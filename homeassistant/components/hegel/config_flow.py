"""Config flow for Hegel integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_MODEL, DEFAULT_PORT, DOMAIN, MODEL_INPUTS

_LOGGER = logging.getLogger(__name__)


class HegelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Hegel amplifiers."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_data: dict[str, Any] = {}
        self._host = ""
        self._model = ""
        self._errors: dict[str, str] = {}

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirmation - only model can be changed."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry_data = {**self._discovered_data, **user_input}
            host = str(entry_data[CONF_HOST])

            try:
                await asyncio.wait_for(
                    asyncio.open_connection(host, DEFAULT_PORT), timeout=2.0
                )
            except (TimeoutError, OSError, ConnectionRefusedError) as err:
                _LOGGER.debug("Cannot connect to %s:%s: %s", host, DEFAULT_PORT, err)
                errors["base"] = "cannot_connect"
            else:
                unique_id = entry_data.get("unique_id") or host
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                entry_data["unique_id"] = unique_id

                title = entry_data.get(CONF_NAME)
                if not title:
                    model = entry_data.get(CONF_MODEL)
                    title = f"Hegel {model}" if model else "Hegel Amplifier"

                return self.async_create_entry(
                    title=title,
                    data=entry_data,
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MODEL, default=self._discovered_data.get(CONF_MODEL)
                ): vol.In(list(MODEL_INPUTS.keys())),
            }
        )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "host": self._discovered_data.get(CONF_HOST, ""),
                "name": self._discovered_data.get(CONF_NAME, ""),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure a config entry."""
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._host = str(user_input[CONF_HOST])
            self._model = str(user_input[CONF_MODEL])

            # Test connection
            try:
                await asyncio.wait_for(
                    asyncio.open_connection(self._host, DEFAULT_PORT), timeout=2.0
                )
            except (TimeoutError, OSError, ConnectionRefusedError) as err:
                _LOGGER.debug(
                    "Cannot connect to %s:%s: %s", self._host, DEFAULT_PORT, err
                )
                self._errors[CONF_HOST] = "cannot_connect"
            else:
                # Determine recognizable title from model
                title = f"Hegel {self._model}" if self._model else "Hegel Amplifier"

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=title,
                    data_updates={
                        CONF_HOST: self._host,
                        CONF_MODEL: self._model,
                    },
                )

            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=self._host): str,
                        vol.Required(CONF_MODEL, default=self._model): vol.In(
                            list(MODEL_INPUTS.keys())
                        ),
                    }
                ),
                errors=self._errors,
            )

        # Pre-populate with current values
        self._host = reconfigure_entry.data[CONF_HOST]
        self._model = str(reconfigure_entry.data.get(CONF_MODEL, ""))

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Required(CONF_MODEL, default=self._model): vol.In(
                        list(MODEL_INPUTS.keys())
                    ),
                }
            ),
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery and pre-fill the user form."""
        upnp = discovery_info.upnp or {}

        host = None
        presentation_url = upnp.get("presentationURL")
        if presentation_url:
            host = URL(presentation_url).host
        else:
            ssdp_location = discovery_info.ssdp_location or ""
            if ssdp_location:
                host = URL(ssdp_location).host

        if not host:
            return self.async_abort(reason="no_host_found")

        # Use UDN (device UUID) instead of USN to avoid duplicates from multiple services
        unique_id = discovery_info.ssdp_udn or discovery_info.ssdp_usn
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        friendly_name = upnp.get("friendlyName", f"Hegel {host}")
        suggested_model = upnp.get("modelName") or ""
        model_default = next(
            (m for m in MODEL_INPUTS if suggested_model.upper().startswith(m.upper())),
            None,
        )

        self._discovered_data = {
            CONF_HOST: host,
            CONF_NAME: friendly_name,
            CONF_MODEL: model_default or list(MODEL_INPUTS.keys())[0],
            "unique_id": unique_id,
        }

        return await self.async_step_discovery_confirm()
