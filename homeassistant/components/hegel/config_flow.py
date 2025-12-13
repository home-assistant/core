"""Config flow for Hegel integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientTimeout
import defusedxml.ElementTree as ET
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
        self._port = DEFAULT_PORT
        self._model = ""
        self._errors: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup or after discovery confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry_data = {**self._discovered_data, **user_input}

            if CONF_PORT not in entry_data:
                entry_data[CONF_PORT] = DEFAULT_PORT

            host = str(entry_data[CONF_HOST])
            port = int(entry_data[CONF_PORT])

            try:
                await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2.0)
            except (TimeoutError, OSError, ConnectionRefusedError) as err:
                _LOGGER.debug("Cannot connect to %s:%s: %s", host, port, err)
                errors[CONF_HOST] = "cannot_connect"
            else:
                unique_id = entry_data.get("unique_id")
                if unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                # Determine recognizable title: prefer discovered name, then model, then generic
                title = entry_data.get(CONF_NAME)  # From SSDP discovery
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
                    CONF_HOST, default=self._discovered_data.get(CONF_HOST, "")
                ): str,
                vol.Optional(
                    CONF_PORT,
                    default=self._discovered_data.get(CONF_PORT, DEFAULT_PORT),
                ): int,
                vol.Optional(
                    CONF_MODEL, default=self._discovered_data.get(CONF_MODEL)
                ): vol.In(list(MODEL_INPUTS.keys())),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure a config entry."""
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._host = str(user_input[CONF_HOST])
            self._port = user_input.get(CONF_PORT, DEFAULT_PORT)
            self._model = str(user_input[CONF_MODEL])

            # Test connection
            try:
                await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port), timeout=2.0
                )
            except (TimeoutError, OSError, ConnectionRefusedError) as err:
                _LOGGER.debug(
                    "Cannot connect to %s:%s: %s", self._host, self._port, err
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
                        CONF_PORT: self._port,
                        CONF_MODEL: self._model,
                    },
                )

            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=self._host): str,
                        vol.Optional(CONF_PORT, default=self._port): int,
                        vol.Optional(CONF_MODEL, default=self._model): vol.In(
                            list(MODEL_INPUTS.keys())
                        ),
                    }
                ),
                errors=self._errors,
            )

        # Pre-populate with current values
        self._host = reconfigure_entry.data[CONF_HOST]
        self._port = reconfigure_entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._model = str(reconfigure_entry.data.get(CONF_MODEL, ""))

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Optional(CONF_PORT, default=self._port): int,
                    vol.Optional(CONF_MODEL, default=self._model): vol.In(
                        list(MODEL_INPUTS.keys())
                    ),
                }
            ),
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery and pre-fill the user form."""
        upnp = getattr(discovery_info, "upnp", {}) or {}

        host = None
        presentation_url = upnp.get("presentationURL")
        if presentation_url:
            host = presentation_url.split("//")[-1].split("/")[0].split(":")[0]
        else:
            ssdp_location = getattr(discovery_info, "ssdp_location", "")
            if ssdp_location:
                host = ssdp_location.split("//")[-1].split("/")[0].split(":")[0]

        if not host:
            return self.async_abort(reason="no_host_found")

        unique_id, mac = await self._async_get_unique_id_from_description(
            discovery_info
        )

        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

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
        }
        if unique_id:
            self._discovered_data["unique_id"] = unique_id
        if mac:
            self._discovered_data["mac"] = mac

        return await self.async_step_user()

    async def _async_get_unique_id_from_description(
        self, discovery_info: SsdpServiceInfo
    ) -> tuple[str | None, str | None]:
        """Fetch device description.xml to get MAC, UDN, or serialNumber."""
        ssdp_location = getattr(discovery_info, "ssdp_location", "")
        if not ssdp_location:
            return None, None

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                ssdp_location, timeout=ClientTimeout(total=5)
            ) as resp:
                text = await resp.text()
        except (TimeoutError, ClientError, OSError) as err:
            _LOGGER.debug("Failed to fetch device description: %s", err)
            return None, None

        # Parse XML for serialNumber or UDN
        try:
            root = ET.fromstring(text)
            serial = next(
                (
                    e.text.strip()
                    for e in root.iter()
                    if e.tag.lower().endswith("serialnumber") and e.text
                ),
                None,
            )
            udn = next(
                (
                    e.text.strip()
                    for e in root.iter()
                    if e.tag.lower().endswith("udn") and e.text
                ),
                None,
            )
            if serial:
                return f"serial:{serial}", None
            if udn:
                return f"udn:{udn}", None

        except ET.ParseError as err:
            _LOGGER.debug("Failed to parse device description XML: %s", err)

        return None, None
