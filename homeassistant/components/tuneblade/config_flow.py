from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
from aiohttp import ClientSession

from .const import DOMAIN
from .tuneblade import TuneBladeApiClient

_LOGGER = logging.getLogger(__name__)


class TuneBladeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manual user setup step."""
        if user_input is not None:
            name = user_input.get("name", "TuneBlade").split("@")[0].strip()
            host = user_input["host"]
            port = user_input["port"]

            unique_id = f"{name}_{host}_{port}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            self._discovery_info = {
                "host": host,
                "port": port,
                "name": name,
            }
            return self.async_create_entry(
                title=name,
                data=self._discovery_info,
            )

        data_schema = vol.Schema(
            {
                vol.Required("host", default='localhost'): str,
                vol.Required("port", default=54412): int,
                vol.Optional("name", default="TuneBlade"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_zeroconf(self, discovery_info: Any) -> FlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovered TuneBlade via Zeroconf: %s", discovery_info)

        host = discovery_info.host
        port = discovery_info.port
        name = discovery_info.name.split("@")[0].strip()

        unique_id = f"{name}_{host}_{port}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self._discovery_info = {
            "host": host,
            "port": port,
            "name": name,
        }

        # Probe the device by attempting to fetch data via TuneBladeApiClient
        session = ClientSession()
        client = TuneBladeApiClient(host, port, session)
        try:
            devices = await client.async_get_data()
        finally:
            await session.close()

        if not devices:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {"name": name}

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Confirm addition after discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.context.get("title_placeholders", {}).get("name", "TuneBlade"),
                data=self._discovery_info,
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self.context.get("title_placeholders", {}).get("name", "TuneBlade"),
                "ip": self._discovery_info["host"],
            },
            data_schema=vol.Schema({}),
            last_step=True,
        )
