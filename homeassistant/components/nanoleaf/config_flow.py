"""Config flow for Nanoleaf integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
import os
from typing import Any, Final, cast

from aionanoleaf import InvalidToken, Nanoleaf, Unauthorized, Unavailable
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp, zeroconf
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.json import load_json, save_json

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# For discovery integration import
CONFIG_FILE: Final = ".nanoleaf.conf"

USER_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Nanoleaf config flow."""

    reauth_entry: config_entries.ConfigEntry | None = None

    VERSION = 1

    def __init__(self) -> None:
        """Initialize a Nanoleaf flow."""
        self.nanoleaf: Nanoleaf

        # For discovery integration import
        self.discovery_conf: dict
        self.device_id: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Nanoleaf flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=USER_SCHEMA, last_step=False
            )
        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        self.nanoleaf = Nanoleaf(
            async_get_clientsession(self.hass), user_input[CONF_HOST]
        )
        try:
            await self.nanoleaf.authorize()
        except Unavailable:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                errors={"base": "cannot_connect"},
                last_step=False,
            )
        except Unauthorized:
            pass
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error connecting to Nanoleaf")
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                last_step=False,
                errors={"base": "unknown"},
            )
        return await self.async_step_link()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle Nanoleaf reauth flow if token is invalid."""
        self.reauth_entry = cast(
            config_entries.ConfigEntry,
            self.hass.config_entries.async_get_entry(self.context["entry_id"]),
        )
        self.nanoleaf = Nanoleaf(
            async_get_clientsession(self.hass), entry_data[CONF_HOST]
        )
        self.context["title_placeholders"] = {"name": self.reauth_entry.title}
        return await self.async_step_link()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle Nanoleaf Zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovered: %s", discovery_info)
        return await self._async_homekit_zeroconf_discovery_handler(discovery_info)

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle Nanoleaf Homekit discovery."""
        _LOGGER.debug("Homekit discovered: %s", discovery_info)
        return await self._async_homekit_zeroconf_discovery_handler(discovery_info)

    async def _async_homekit_zeroconf_discovery_handler(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle Nanoleaf Homekit and Zeroconf discovery."""
        return await self._async_discovery_handler(
            discovery_info.host,
            discovery_info.name.replace(f".{discovery_info.type}", ""),
            discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID],
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle Nanoleaf SSDP discovery."""
        _LOGGER.debug("SSDP discovered: %s", discovery_info)
        return await self._async_discovery_handler(
            discovery_info.ssdp_headers["_host"],
            discovery_info.ssdp_headers["nl-devicename"],
            discovery_info.ssdp_headers["nl-deviceid"],
        )

    async def _async_discovery_handler(
        self, host: str, name: str, device_id: str
    ) -> FlowResult:
        """Handle Nanoleaf discovery."""
        # The name is unique and printed on the device and cannot be changed.
        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured({CONF_HOST: host})

        # Import from discovery integration
        self.device_id = device_id
        self.discovery_conf = cast(
            dict,
            await self.hass.async_add_executor_job(
                load_json, self.hass.config.path(CONFIG_FILE)
            ),
        )
        auth_token: str | None = self.discovery_conf.get(self.device_id, {}).get(
            "token",  # >= 2021.4
            self.discovery_conf.get(host, {}).get("token"),  # < 2021.4
        )
        if auth_token is not None:
            self.nanoleaf = Nanoleaf(
                async_get_clientsession(self.hass), host, auth_token
            )
            _LOGGER.warning(
                "Importing Nanoleaf %s from the discovery integration", name
            )
            return await self.async_setup_finish(discovery_integration_import=True)
        self.nanoleaf = Nanoleaf(async_get_clientsession(self.hass), host)
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_link()

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Nanoleaf link step."""
        if user_input is None:
            return self.async_show_form(step_id="link")

        try:
            await self.nanoleaf.authorize()
        except Unauthorized:
            return self.async_show_form(
                step_id="link", errors={"base": "not_allowing_new_tokens"}
            )
        except Unavailable:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error authorizing Nanoleaf")
            return self.async_show_form(step_id="link", errors={"base": "unknown"})

        if self.reauth_entry is not None:
            self.hass.config_entries.async_update_entry(
                self.reauth_entry,
                data={
                    **self.reauth_entry.data,
                    CONF_TOKEN: self.nanoleaf.auth_token,
                },
            )
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return await self.async_setup_finish()

    async def async_setup_finish(
        self, discovery_integration_import: bool = False
    ) -> FlowResult:
        """Finish Nanoleaf config flow."""
        try:
            await self.nanoleaf.get_info()
        except Unavailable:
            return self.async_abort(reason="cannot_connect")
        except InvalidToken:
            return self.async_abort(reason="invalid_token")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Nanoleaf at %s", self.nanoleaf.host
            )
            return self.async_abort(reason="unknown")
        name = self.nanoleaf.name

        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured({CONF_HOST: self.nanoleaf.host})

        if discovery_integration_import:
            if self.nanoleaf.host in self.discovery_conf:
                self.discovery_conf.pop(self.nanoleaf.host)
            if self.device_id in self.discovery_conf:
                self.discovery_conf.pop(self.device_id)
            _LOGGER.info(
                "Successfully imported Nanoleaf %s from the discovery integration",
                name,
            )
            if self.discovery_conf:
                await self.hass.async_add_executor_job(
                    save_json, self.hass.config.path(CONFIG_FILE), self.discovery_conf
                )
            else:
                await self.hass.async_add_executor_job(
                    os.remove, self.hass.config.path(CONFIG_FILE)
                )

        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: self.nanoleaf.host,
                CONF_TOKEN: self.nanoleaf.auth_token,
            },
        )
