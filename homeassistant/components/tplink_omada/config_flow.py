"""Config flow for TP-Link Omada integration."""
from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any, NamedTuple

from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)
from tplink_omada_client.omadaclient import OmadaClient, OmadaSite
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_SITE = "site"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def create_omada_client(
    hass: HomeAssistant, data: MappingProxyType[str, Any]
) -> OmadaClient:
    """Create a TP-Link Omada client API for the given config entry."""
    host = data[CONF_HOST]
    verify_ssl = bool(data[CONF_VERIFY_SSL])
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    websession = async_get_clientsession(hass, verify_ssl=verify_ssl)
    return OmadaClient(host, username, password, websession=websession)


class HubInfo(NamedTuple):
    """Basic controller information."""

    controller_id: str
    name: str
    sites: list[OmadaSite]


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> HubInfo:
    """Validate the user input allows us to connect."""

    client = await create_omada_client(hass, MappingProxyType(data))
    controller_id = await client.login()
    name = await client.get_controller_name()
    sites = await client.get_sites()

    return HubInfo(controller_id, name, sites)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TP-Link Omada."""

    VERSION = 1

    def __init__(self) -> None:
        """Create the config flow for a new integration."""
        self._omada_opts: dict[str, Any] = {}
        self._sites: list[OmadaSite] = []
        self._display_name: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await _validate_input(self.hass, user_input)
        except ConnectionFailed:
            errors["base"] = "cannot_connect"
        except LoginFailed:
            errors["base"] = "invalid_auth"
        except UnsupportedControllerVersion:
            errors["base"] = "unsupported_controller"
        except OmadaClientException as ex:
            _LOGGER.exception("Unexpected API error: %s", ex)
            errors["base"] = "unknown"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self._omada_opts.update(user_input)
            self._display_name = f"{info.name} ({info.sites[0].name})"
            if len(info.sites) < 1:
                errors["base"] = "no_sites_found"
            else:
                self._sites = info.sites
                if len(self._sites) > 1:
                    return await self.async_step_site()
                return await self.async_step_site({CONF_SITE: self._sites[0].id})

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_site(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step to select site to manage."""

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_SITE, "site"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=s.id, label=s.name)
                                for s in self._sites
                            ],
                            multiple=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            )

            return self.async_show_form(step_id="site", data_schema=schema)

        self._omada_opts.update(user_input)
        return self.async_create_entry(title=self._display_name, data=self._omada_opts)
