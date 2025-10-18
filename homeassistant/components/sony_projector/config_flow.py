"""Config flow for the Sony Projector integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .client import (
    DiscoveredProjector,
    ProjectorClient,
    ProjectorClientError,
    async_discover,
)
from .const import (
    CONF_MODEL,
    CONF_SERIAL,
    CONF_TITLE,
    DEFAULT_NAME,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SonyProjectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sony Projector."""

    VERSION = 1
    _reauth_entry: ConfigEntry | None = None
    _discovered: dict[str, DiscoveredProjector]
    _discovery_task: asyncio.Task[list[DiscoveredProjector]] | None
    _pending_discovery: DiscoveredProjector | None
    _pending_discovery_title: str | None

    def __init__(self) -> None:
        """Initialize the Sony Projector config flow."""

        super().__init__()
        self._discovered = {}
        self._discovery_task = None
        self._pending_discovery = None
        self._pending_discovery_title = None

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""

        return self.async_show_menu(
            step_id="user",
            menu_options=["manual", "scan"],
        )

    async def async_step_manual(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual host configuration."""

        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input.get(CONF_NAME)
            return await self._async_create_entry_from_host(host, name, "manual")

        data_schema = vol.Schema(
            {vol.Required(CONF_HOST): str, vol.Optional(CONF_NAME): str}
        )
        return self.async_show_form(
            step_id="manual",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_scan(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery of projectors on the network."""

        if user_input is not None and CONF_HOST in user_input:
            return await self.async_step_scan_results(user_input)

        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                async_discover(self.hass.loop, timeout=DISCOVERY_TIMEOUT)
            )
            return self.async_show_progress(
                step_id="scan",
                progress_action="listen_for_projectors",
                description_placeholders={"timeout": str(int(DISCOVERY_TIMEOUT))},
            )

        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="scan",
                progress_action="listen_for_projectors",
                description_placeholders={"timeout": str(int(DISCOVERY_TIMEOUT))},
            )

        try:
            discovered = await self._discovery_task
        except Exception as err:  # noqa: BLE001 - library raises broad exceptions
            _LOGGER.debug("Unexpected discovery failure: %s", err)
            discovered = []
        finally:
            self._discovery_task = None

        current_unique_ids = self._async_current_ids(include_ignore=False)
        self._discovered = {}
        for device in discovered:
            unique_id = device.serial or device.host
            if unique_id in current_unique_ids:
                continue
            self._discovered[device.host] = device
        return self.async_show_progress_done(next_step_id="scan_results")

    async def async_step_scan_results(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Present discovered projectors to the user."""

        errors: dict[str, str] = {}

        if user_input is not None and CONF_HOST in user_input:
            selected = user_input[CONF_HOST]
            device = self._discovered[selected]
            return await self._async_create_entry_from_host(
                device.host, device.model, "scan"
            )

        if not self._discovered:
            errors["base"] = "no_devices_found"

        options = {
            host: _format_discovery_option(device)
            for host, device in self._discovered.items()
        }

        data_schema = vol.Schema(
            {vol.Required(CONF_HOST): vol.In(options) if options else str}
        )

        return self.async_show_form(
            step_id="scan",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"count": str(len(self._discovered))},
        )

    async def async_step_integration_discovery(
        self, discovery_info: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle passive SDCP discovery."""

        host = discovery_info[CONF_HOST]
        model = discovery_info.get(CONF_MODEL)
        serial = discovery_info.get(CONF_SERIAL)
        title = discovery_info.get(CONF_TITLE)

        device = DiscoveredProjector(host=host, model=model, serial=serial)
        unique_id = serial or host
        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})

        self._pending_discovery = device
        self._pending_discovery_title = title or model

        self.context["title_placeholders"] = {"name": title or model or DEFAULT_NAME}

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered projector."""

        assert self._pending_discovery is not None

        if user_input is None:
            suggested = (
                self._pending_discovery_title
                or self._pending_discovery.model
                or DEFAULT_NAME
            )
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "name": suggested,
                    "host": self._pending_discovery.host,
                },
            )

        return await self._async_create_entry_from_host(
            self._pending_discovery.host,
            self._pending_discovery_title or self._pending_discovery.model,
            "confirm",
        )

    async def async_step_import(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle YAML import for legacy configurations."""

        host = user_input[CONF_HOST]
        name = user_input.get(CONF_NAME)
        return await self._async_create_entry_from_host(host, name, "manual")

    async def async_step_reauth(self, data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication."""

        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def _async_create_entry_from_host(
        self,
        host: str,
        suggested_title: str | None,
        source_step: str,
    ) -> ConfigFlowResult:
        """Validate projector connectivity and create the entry."""

        client = ProjectorClient(host)

        try:
            await client.async_refresh_device_info()
        except ProjectorClientError:
            _LOGGER.debug("Unable to retrieve projector information for host %s", host)

        try:
            await client.async_get_state()
        except ProjectorClientError:
            schema = vol.Schema(
                {vol.Required(CONF_HOST): str, vol.Optional(CONF_NAME): str}
            )
            return self.async_show_form(
                step_id=source_step,
                data_schema=schema,
                errors={"base": "cannot_connect"},
            )

        unique_id = client.serial or host
        await self.async_set_unique_id(unique_id, raise_on_progress=False)

        if self._reauth_entry is not None:
            self._abort_if_unique_id_mismatch(reason="wrong_device")
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data_updates={
                    CONF_HOST: host,
                    CONF_SERIAL: client.serial,
                    CONF_MODEL: client.model,
                },
            )

        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        title = suggested_title or client.model or DEFAULT_NAME

        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: host,
                CONF_SERIAL: client.serial,
                CONF_MODEL: client.model,
                CONF_TITLE: title,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""

        return SonyProjectorOptionsFlow(config_entry)


class SonyProjectorOptionsFlow(OptionsFlow):
    """Handle options for the Sony Projector integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""

        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options flow entry point."""

        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))


def _format_discovery_option(device: DiscoveredProjector) -> str:
    """Return a user facing label for a discovered device."""

    serial = device.serial or "unknown"
    model = device.model or DEFAULT_NAME
    return f"{model} ({serial}) @ {device.host}"
