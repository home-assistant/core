"""Config flow for TP-Link Omada integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from types import MappingProxyType
from typing import Any, NamedTuple
from urllib.parse import urlsplit

from aiohttp import CookieJar
from tplink_omada_client import OmadaClient, OmadaSite
from tplink_omada_client.clients import OmadaWirelessClient
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

from .const import DOMAIN
from .controller import OmadaSiteController

_LOGGER = logging.getLogger(__name__)

CONF_SITE = "site"

OPT_DEVICE_TRACKER = "device_tracker"
OPT_TRACKED_CLIENTS = "tracked_clients"
OPT_SCANNED_CLIENTS = "scanned_clients"

_STEP_DEVICE_TRACKER = "device_tracker"

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

    host: str = data[CONF_HOST]
    verify_ssl = bool(data[CONF_VERIFY_SSL])

    if not host.lower().startswith(("http://", "https://")):
        host = "https://" + host
    host_parts = urlsplit(host)
    if (
        host_parts.hostname
        and re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", host_parts.hostname)
        is not None
    ):
        # TP-Link API uses cookies for login session, so an unsafe cookie jar is required for IP addresses
        websession = async_create_clientsession(
            hass, cookie_jar=CookieJar(unsafe=True), verify_ssl=verify_ssl
        )
    else:
        websession = async_get_clientsession(hass, verify_ssl=verify_ssl)

    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]

    return OmadaClient(host, username, password, websession=websession)


class HubInfo(NamedTuple):
    """Discovered controller information."""

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


class TpLinkOmadaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TP-Link Omada."""

    VERSION = 1

    def __init__(self) -> None:
        """Create the config flow for a new integration."""
        self._omada_opts: dict[str, Any] = {}
        self._sites: list[OmadaSite] = []
        self._controller_name = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        info = None
        if user_input is not None:
            info = await self._test_login(user_input, errors)

        if info is None or user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(info.controller_id)
        self._abort_if_unique_id_configured()

        self._omada_opts.update(user_input)
        self._sites = info.sites
        self._controller_name = info.name
        if len(self._sites) > 1:
            return await self.async_step_site()
        return await self.async_step_site({CONF_SITE: self._sites[0].id})

    async def async_step_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        site_name = next(
            site for site in self._sites if site.id == user_input["site"]
        ).name
        display_name = f"{self._controller_name} ({site_name})"

        return self.async_create_entry(title=display_name, data=self._omada_opts)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._omada_opts = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self._omada_opts.update(user_input)
            info = await self._test_login(self._omada_opts, errors)

            if info is not None:
                # Auth successful - update the config entry with the new credentials
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                assert entry is not None
                self.hass.config_entries.async_update_entry(
                    entry, data=self._omada_opts
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def _test_login(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> HubInfo | None:
        try:
            info = await _validate_input(self.hass, data)
            if len(info.sites) > 0:
                return info
            errors["base"] = "no_sites_found"

        except ConnectionFailed:
            errors["base"] = "cannot_connect"
        except LoginFailed:
            errors["base"] = "invalid_auth"
        except UnsupportedControllerVersion:
            errors["base"] = "unsupported_controller"
        except OmadaClientException as ex:
            _LOGGER.error("Unexpected API error: %s", ex)
            errors["base"] = "unknown"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Options flow for TP-Link Omada."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the top-level options."""

        self.options.update(user_input or {})
        device_tracker_enabled = self.options.get(OPT_DEVICE_TRACKER, False)

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            OPT_DEVICE_TRACKER,
                            default=device_tracker_enabled,
                        ): bool
                    }
                ),
            )

        if device_tracker_enabled:
            return await self.async_step_device_tracker()

        return self.async_create_entry(data=self.options)

    async def async_step_device_tracker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the device tracker options."""
        errors = {}

        if user_input is not None:
            self.options.update(user_input)
            if (
                len(self.options[OPT_TRACKED_CLIENTS]) == 0
                and len(self.options[OPT_SCANNED_CLIENTS]) == 0
            ):
                errors[OPT_TRACKED_CLIENTS] = "no_clients_selected"

        if user_input is None or errors:
            controller: OmadaSiteController = self.hass.data[DOMAIN][
                self.config_entry.entry_id
            ]

            site_client = controller.omada_client
            # Get the known Wi-Fi clients, in alphabetical order moving un-named clients to the end of the list
            clients: list[OmadaWirelessClient] = sorted(
                [
                    client
                    async for client in site_client.get_known_clients()
                    if isinstance(client, OmadaWirelessClient)
                ],
                key=lambda c: (0 if c.name != c.mac else 1, c.name),
            )

            schema = vol.Schema(
                {
                    vol.Optional(
                        OPT_SCANNED_CLIENTS,
                        default=self.options.get(OPT_SCANNED_CLIENTS, []),
                    ): _get_clients_selector(clients),
                    vol.Optional(
                        OPT_TRACKED_CLIENTS,
                        default=self.options.get(OPT_TRACKED_CLIENTS, []),
                    ): _get_clients_selector(clients),
                }
            )

            return self.async_show_form(
                step_id=_STEP_DEVICE_TRACKER, data_schema=schema, errors=errors
            )

        return self.async_create_entry(data=self.options)


def _get_clients_selector(
    clients: list[OmadaWirelessClient],
) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=c.mac, label=c.name) for c in clients
            ],
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )
