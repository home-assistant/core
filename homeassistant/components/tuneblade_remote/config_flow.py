"""Adds config flow for TuneBlade Remote."""

from __future__ import annotations

import logging
from typing import Any

from pytuneblade import TuneBladeApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TuneBladeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for TuneBlade Remote."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._discovery_info: dict[str, Any] = {}
        self._title_placeholders: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual user setup step."""
        errors = {}

        if user_input is not None:
            name = user_input["name"].strip()
            host = user_input["host"]
            port = user_input["port"]

            session = async_get_clientsession(self.hass)
            client = TuneBladeApiClient(host, port, session)
            try:
                devices = await client.async_get_data()
            except Exception:
                _LOGGER.exception("Failed to connect to TuneBlade")
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "cannot_connect"

            if not errors:
                unique_id = f"{name}_{host}_{port}"
                await self.async_set_unique_id(unique_id)
                await self.async_abort_if_unique_id_configured()  # type: ignore[attr-defined]

                return self.async_create_entry(
                    title=name,
                    data={
                        "host": host,
                        "port": port,
                        "name": name,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required("host", default="localhost"): str,
                vol.Required("port", default=54412): int,
                vol.Optional("name", default="TuneBlade"): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovered TuneBlade via Zeroconf: %s", discovery_info)

        host = discovery_info.host
        port = discovery_info.port
        name = discovery_info.name.split("@")[0].strip()

        unique_id = f"{name}_{host}_{port}"
        await self.async_set_unique_id(unique_id)
        await self.async_abort_if_unique_id_configured()  # type: ignore[attr-defined]

        self._discovery_info = {
            "host": host,
            "port": port,
            "name": name,
        }

        session = async_get_clientsession(self.hass)
        client = TuneBladeApiClient(host, port, session)
        try:
            devices = await client.async_get_data()
        except Exception:
            _LOGGER.exception("Failed to connect to TuneBlade via zeroconf")
            return self.async_abort(reason="cannot_connect")

        if not devices:
            return self.async_abort(reason="cannot_connect")

        self._title_placeholders = {"name": name}

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm addition after discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title_placeholders.get("name", "TuneBlade"),
                data=self._discovery_info,
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._title_placeholders.get("name", "TuneBlade"),
                "ip": self._discovery_info["host"],
            },
            data_schema=vol.Schema({}),
            last_step=True,
        )
