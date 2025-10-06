# config_flow.py
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional, Tuple

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_MODEL, DEFAULT_PORT, DOMAIN, MODEL_INPUTS

_LOGGER = logging.getLogger(__name__)


class HegelFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Hegel amplifiers."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        self._discovered_data: dict[str, Any] = {}
        self._host = ""
        self._port = DEFAULT_PORT
        self._name = ""
        self._model = ""
        self._errors: dict[str, str] = {}

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup or after discovery confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry_data = {**self._discovered_data, **user_input}

            host = entry_data[CONF_HOST]
            port = entry_data.get(CONF_PORT, DEFAULT_PORT)

            try:
                await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2.0)
            except Exception:
                _LOGGER.debug("Cannot connect to %s:%s", host, port)
                errors[CONF_HOST] = "cannot_connect"
            else:
                unique_id = entry_data.get("unique_id")
                if unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=entry_data.get(CONF_NAME, f"Hegel {host}"),
                    data=entry_data,
                )

        # Build form schema
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
                    CONF_NAME, default=self._discovered_data.get(CONF_NAME, "")
                ): str,
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
            self._host = user_input[CONF_HOST]
            self._port = user_input.get(CONF_PORT, DEFAULT_PORT)
            self._name = user_input.get(CONF_NAME, f"Hegel {self._host}")
            self._model = user_input.get(CONF_MODEL)

            # Test connection
            try:
                await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port), timeout=2.0
                )
            except Exception:
                _LOGGER.debug("Cannot connect to %s:%s", self._host, self._port)
                self._errors[CONF_HOST] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_NAME: self._name,
                        CONF_MODEL: self._model,
                    },
                )

            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=self._host): str,
                        vol.Optional(CONF_PORT, default=self._port): int,
                        vol.Optional(CONF_NAME, default=self._name): str,
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
        self._name = reconfigure_entry.data.get(CONF_NAME, f"Hegel {self._host}")
        self._model = reconfigure_entry.data.get(CONF_MODEL)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Optional(CONF_PORT, default=self._port): int,
                    vol.Optional(CONF_NAME, default=self._name): str,
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
    ) -> Tuple[Optional[str], Optional[str]]:
        """Fetch device description.xml to get MAC, UDN, or serialNumber."""
        ssdp_location = getattr(discovery_info, "ssdp_location", "")
        if not ssdp_location:
            return None, None

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(ssdp_location, timeout=5) as resp:
                text = await resp.text()
        except Exception:
            return None, None

        # Try MAC regex
        mac_match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})", text)
        if mac_match:
            mac = mac_match.group(0).lower()
            return f"mac:{mac.replace(':','')}", mac

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
                # use udn as stable id if mac/serial absent
                return f"udn:{udn}", None
        except Exception:
            pass

        return None, None
