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

                return self.async_create_entry(
                    title=entry_data[CONF_NAME],
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

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery and pre-fill the user form."""
        upnp = discovery_info.upnp or {}

        url = upnp.get("presentationURL")
        if not url:
            ssdp_location = discovery_info.ssdp_location or ""
            if ssdp_location:
                url = ssdp_location

        if not url:
            return self.async_abort(reason="no_host_found")
        host = URL(url).host

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
