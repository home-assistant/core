"""Config flow for OctoPrint integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
from pyoctoprintapi import ApiError, OctoprintClient, OctoprintException
import voluptuous as vol
from yarl import URL

from homeassistant import config_entries, data_entry_flow, exceptions
from homeassistant.components import ssdp, zeroconf
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(
    username="", host="", port=80, path="/", ssl=False, verify_ssl=True
):
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): str,
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Required(CONF_PATH, default=path): str,
            vol.Required(CONF_SSL, default=ssl): bool,
            vol.Required(CONF_VERIFY_SSL, default=verify_ssl): bool,
        },
        extra=vol.ALLOW_EXTRA,
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OctoPrint."""

    VERSION = 1

    api_key_task: asyncio.Task[None] | None = None
    discovery_schema: vol.Schema | None = None
    _reauth_data: dict[str, Any] | None = None
    _user_input: dict[str, Any] | None = None

    def __init__(self) -> None:
        """Handle a config flow for OctoPrint."""
        self._sessions: list[aiohttp.ClientSession] = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        # When coming back from the progress steps, the user_input is stored in the
        # instance variable instead of being passed in
        if user_input is None and self._user_input:
            user_input = self._user_input

        if user_input is None:
            data = self.discovery_schema or _schema_with_defaults()
            return self.async_show_form(step_id="user", data_schema=data)

        if CONF_API_KEY in user_input:
            errors = {}
            try:
                return await self._finish_config(user_input)
            except data_entry_flow.AbortFlow as err:
                raise err from None
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    errors=errors,
                    data_schema=_schema_with_defaults(
                        user_input.get(CONF_USERNAME),
                        user_input[CONF_HOST],
                        user_input[CONF_PORT],
                        user_input[CONF_PATH],
                        user_input[CONF_SSL],
                        user_input[CONF_VERIFY_SSL],
                    ),
                )

        self._user_input = user_input
        return await self.async_step_get_api_key()

    async def async_step_get_api_key(self, user_input=None):
        """Get an Application Api Key."""
        if not self.api_key_task:
            self.api_key_task = self.hass.async_create_task(self._async_get_auth_key())
        if not self.api_key_task.done():
            return self.async_show_progress(
                step_id="get_api_key",
                progress_action="get_api_key",
                progress_task=self.api_key_task,
            )

        try:
            await self.api_key_task
        except OctoprintException as err:
            _LOGGER.exception("Failed to get an application key: %s", err)
            return self.async_show_progress_done(next_step_id="auth_failed")
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Failed to get an application key : %s", err)
            return self.async_show_progress_done(next_step_id="auth_failed")
        finally:
            self.api_key_task = None

        return self.async_show_progress_done(next_step_id="user")

    async def _finish_config(self, user_input: dict):
        """Finish the configuration setup."""
        existing_entry = await self.async_set_unique_id(self.unique_id)
        if existing_entry is not None:
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            # Reload the config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        octoprint = self._get_octoprint_client(user_input)
        octoprint.set_api_key(user_input[CONF_API_KEY])

        try:
            discovery = await octoprint.get_discovery_info()
        except ApiError as err:
            _LOGGER.error("Failed to connect to printer")
            raise CannotConnect from err

        await self.async_set_unique_id(discovery.upnp_uuid, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    async def async_step_auth_failed(self, user_input):
        """Handle api fetch failure."""
        return self.async_abort(reason="auth_failed")

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle discovery flow."""
        uuid = discovery_info.properties["uuid"]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        self.context.update(
            {
                "title_placeholders": {CONF_HOST: discovery_info.host},
                "configuration_url": (
                    f"http://{discovery_info.host}:{discovery_info.port}"
                    f"{discovery_info.properties[CONF_PATH]}"
                ),
            }
        )

        self.discovery_schema = _schema_with_defaults(
            host=discovery_info.host,
            port=discovery_info.port,
            path=discovery_info.properties[CONF_PATH],
        )

        return await self.async_step_user()

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle ssdp discovery flow."""
        uuid = discovery_info.upnp["UDN"][5:]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        url = URL(discovery_info.upnp["presentationURL"])
        self.context.update(
            {
                "title_placeholders": {CONF_HOST: url.host},
                "configuration_url": discovery_info.upnp["presentationURL"],
            }
        )

        self.discovery_schema = _schema_with_defaults(
            host=url.host,
            path=url.path,
            port=url.port,
            ssl=url.scheme == "https",
        )

        return await self.async_step_user()

    async def async_step_reauth(self, config: Mapping[str, Any]) -> FlowResult:
        """Handle reauthorization request from Octoprint."""
        self._reauth_data = dict(config)

        self.context.update(
            {
                "title_placeholders": {CONF_HOST: config[CONF_HOST]},
            }
        )

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization flow."""
        assert self._reauth_data is not None

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_USERNAME, default=self._reauth_data[CONF_USERNAME]
                        ): str,
                    }
                ),
            )

        self._reauth_data[CONF_USERNAME] = user_input[CONF_USERNAME]

        self._user_input = self._reauth_data
        return await self.async_step_get_api_key()

    async def _async_get_auth_key(self):
        """Get application api key."""
        octoprint = self._get_octoprint_client(self._user_input)

        self._user_input[CONF_API_KEY] = await octoprint.request_app_key(
            "Home Assistant", self._user_input[CONF_USERNAME], 300
        )

    def _get_octoprint_client(self, user_input: dict) -> OctoprintClient:
        """Build an octoprint client from the user_input."""
        verify_ssl = user_input.get(CONF_VERIFY_SSL, True)

        connector = aiohttp.TCPConnector(
            force_close=True,
            ssl=get_default_no_verify_context()
            if not verify_ssl
            else get_default_context(),
        )
        session = aiohttp.ClientSession(connector=connector)
        self._sessions.append(session)

        return OctoprintClient(
            host=user_input[CONF_HOST],
            session=session,
            port=user_input[CONF_PORT],
            ssl=user_input[CONF_SSL],
            path=user_input[CONF_PATH],
        )

    def async_remove(self):
        """Detach the session."""
        for session in self._sessions:
            session.detach()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
