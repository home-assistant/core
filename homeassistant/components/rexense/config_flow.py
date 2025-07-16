"""Config flow for Rexense integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from aiorexense.api import get_basic_info
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RexenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rexense."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.device_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual user configuration (from UI)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            session = aiohttp_client.async_get_clientsession(self.hass)
            try:
                device_id, model, sw_build_id, feature_map = await get_basic_info(
                    host, port, session
                )
            except (TimeoutError, ClientError) as err:
                _LOGGER.error(
                    "Error connecting to Rexense device at %s:%s - %s", host, port, err
                )
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )

                self.device_data = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    "device_id": device_id,
                    CONF_MODEL: model,
                    "sw_build_id": sw_build_id,
                    "feature_map": feature_map,
                }

                return self.async_create_entry(
                    title=f"{model} ({device_id})",
                    data=self.device_data,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        host: str
        port: int
        model: str
        device_id: str
        sw_build_id: str
        feature_map: list[Any]

        # Retrieve the ConfigEntry being reconfigured
        entry_id = self.context.get("entry_id")
        if not entry_id:
            # Should never happen, but abort if we can't find it
            return self.async_abort(reason="unknown")

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return self.async_abort(reason="unknown")

        # On form submission, write back updated data
        if user_input is not None:
            host = self.device_data[CONF_HOST]
            port = self.device_data.get(CONF_PORT, DEFAULT_PORT)
            device_id = str(self.device_data.get("device_id", ""))
            model = self.device_data.get(CONF_MODEL, "Rexense Device")
            sw_build_id = self.device_data.get("sw_build_id", "")
            feature_map = self.device_data.get("feature_map", [])
            # Update the entry with new data
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_HOST: host,
                    CONF_PORT: port,
                    "device_id": device_id,
                    CONF_MODEL: model,
                    "sw_build_id": sw_build_id,
                    "feature_map": feature_map,
                },
            )

        # Populate self.device_data so downstream steps can read it
        host = entry.data[CONF_HOST]
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        model = entry.data.get(CONF_MODEL, "")
        device_id = str(entry.data.get("device_id", ""))
        sw_build_id = entry.data.get("sw_build_id", "")
        feature_map = entry.data.get("feature_map", [])

        self.device_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            "device_id": device_id,
            CONF_MODEL: model,
            "sw_build_id": sw_build_id,
            "feature_map": feature_map,
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=host): cv.string,
                vol.Optional(CONF_PORT, default=port): cv.port,
            }
        )
        _LOGGER.debug("Reconfiguring Rexense device %s at %s:%s", device_id, host, port)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            description_placeholders={
                "device_id": device_id,
                CONF_MODEL: model,
                CONF_PORT: host,
            },
            errors={},
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf discovery."""
        if discovery_info.type != "_rexense._tcp.local.":
            return self.async_abort(reason="not_rexense_service")
        host = discovery_info.host or (
            discovery_info.addresses[0] if discovery_info.addresses else None
        )
        if not host:
            return self.async_abort(reason="no_host_found")
        port = discovery_info.port or DEFAULT_PORT

        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            device_id, model, sw_build_id, feature_map = await get_basic_info(
                host, port, session
            )
        except (TimeoutError, ClientError):
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})

        self.device_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            "device_id": device_id,
            CONF_MODEL: model,
            "sw_build_id": sw_build_id,
            "feature_map": feature_map,
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the confirmation step for discovered device."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"{self.device_data['model']} ({self.device_data['device_id']})",
                data=self.device_data,
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                CONF_HOST: self.device_data[CONF_HOST],
                CONF_MODEL: self.device_data[CONF_MODEL],
            },
        )
