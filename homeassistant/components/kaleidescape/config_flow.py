"""Config flow for Kaleidescape."""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from . import KaleidescapeDeviceInfo, UnsupportedError, validate_host
from .const import DEFAULT_HOST, DOMAIN, NAME as KALEIDESCAPE_NAME

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNSUPPORTED = "unsupported"


class KaleidescapeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Kaleidescape integration."""

    VERSION = 1

    discovered_device: KaleidescapeDeviceInfo

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated device additions."""
        errors = {}
        host = DEFAULT_HOST

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            try:
                info = await validate_host(host)
                if info.server_only:
                    raise UnsupportedError
            except ConnectionError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except UnsupportedError:
                errors["base"] = ERROR_UNSUPPORTED
            else:
                host = info.host

                await self.async_set_unique_id(info.serial, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                return self.async_create_entry(
                    title=f"{KALEIDESCAPE_NAME} ({info.name})",
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovered device."""
        host = cast(str, urlparse(discovery_info.ssdp_location).hostname)
        serial_number = discovery_info.upnp[ssdp.ATTR_UPNP_SERIAL]

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            self.discovered_device = await validate_host(host)
            if self.discovered_device.server_only:
                raise UnsupportedError
        except ConnectionError:
            return self.async_abort(reason=ERROR_CANNOT_CONNECT)
        except UnsupportedError:
            return self.async_abort(reason=ERROR_UNSUPPORTED)

        self.context.update(
            {
                "title_placeholders": {
                    "name": self.discovered_device.name,
                    "model": self.discovered_device.model,
                }
            }
        )

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle addition of discovered device."""
        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={
                    "name": self.discovered_device.name,
                    "model": self.discovered_device.model,
                },
                errors={},
            )

        return self.async_create_entry(
            title=f"{KALEIDESCAPE_NAME} ({self.discovered_device.name})",
            data={CONF_HOST: self.discovered_device.host},
        )
