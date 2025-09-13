# config_flow.py
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional, Tuple

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import DOMAIN, CONF_MODEL, MODEL_INPUTS, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


class HegelFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Hegel amplifiers."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        self._discovered_data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
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

        defaults = {
            CONF_HOST: self._discovered_data.get(CONF_HOST, ""),
            CONF_MODEL: self._discovered_data.get(CONF_MODEL, list(MODEL_INPUTS.keys())[0]),
            CONF_PORT: self._discovered_data.get(CONF_PORT, DEFAULT_PORT),
            CONF_NAME: self._discovered_data.get(CONF_NAME, "Hegel Amplifier"),
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                vol.Required(CONF_MODEL, default=defaults[CONF_MODEL]): vol.In(list(MODEL_INPUTS.keys())),
                vol.Optional(CONF_PORT, default=defaults[CONF_PORT]): int,
                vol.Optional(CONF_NAME, default=defaults[CONF_NAME]): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
        
    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo):
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
    
        unique_id, mac = await self._async_get_unique_id_from_description(discovery_info)
    
        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
    
        friendly_name = upnp.get("friendlyName", f"Hegel {host}")
        suggested_model = upnp.get("modelName") or ""
        model_default = next((m for m in MODEL_INPUTS if suggested_model.upper().startswith(m.upper())), None)
    
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
            serial = next((e.text.strip() for e in root.iter() if e.tag.lower().endswith("serialnumber") and e.text), None)
            udn = next((e.text.strip() for e in root.iter() if e.tag.lower().endswith("udn") and e.text), None)
            if serial:
                return f"serial:{serial}", None
            if udn:
                # use udn as stable id if mac/serial absent
                return f"udn:{udn}", None
        except Exception:
            pass

        return None, None
