"""Config flow for Wyoming integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import hassio, zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .data import WyomingService

_LOGGER = logging.getLogger()

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wyoming integration."""

    VERSION = 1

    _hassio_discovery: hassio.HassioServiceInfo
    _service: WyomingService | None = None
    _name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        service = await WyomingService.create(
            user_input[CONF_HOST],
            user_input[CONF_PORT],
        )

        if service is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        if name := service.get_name():
            return self.async_create_entry(title=name, data=user_input)

        return self.async_abort(reason="no_services")

    async def async_step_hassio(
        self, discovery_info: hassio.HassioServiceInfo
    ) -> FlowResult:
        """Handle Supervisor add-on discovery."""
        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured()

        self._hassio_discovery = discovery_info
        self.context.update(
            {
                "title_placeholders": {"name": discovery_info.name},
                "configuration_url": f"homeassistant://hassio/addon/{discovery_info.slug}/info",
            }
        )
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Supervisor discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uri = urlparse(self._hassio_discovery.config["uri"])
            if service := await WyomingService.create(uri.hostname, uri.port):
                if not service.has_services():
                    return self.async_abort(reason="no_services")

                return self.async_create_entry(
                    title=self._hassio_discovery.name,
                    data={CONF_HOST: uri.hostname, CONF_PORT: uri.port},
                )

            errors = {"base": "cannot_connect"}

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery.name},
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovery info: %s", discovery_info)
        if discovery_info.port is None:
            return self.async_abort(reason="no_port")

        service = await WyomingService.create(discovery_info.host, discovery_info.port)
        if (service is None) or (not (name := service.get_name())):
            # No supported services
            return self.async_abort(reason="no_services")

        self._name = name

        # Use zeroconf name + service name as unique id.
        # The satellite will use its own MAC as the zeroconf name by default.
        unique_id = f"{discovery_info.name}_{self._name}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self.context[CONF_NAME] = self._name
        self.context["title_placeholders"] = {"name": self._name}

        self._service = service
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by zeroconf."""
        assert self._service is not None
        assert self._name is not None

        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self._name},
                errors={},
            )

        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._service.host,
                CONF_PORT: self._service.port,
            },
        )
