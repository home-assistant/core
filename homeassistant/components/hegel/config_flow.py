"""Config flow for Hegel integration."""

from __future__ import annotations

import logging
from typing import Any

from hegel_ip_client import HegelClient
from hegel_ip_client.exceptions import HegelConnectionError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_MODEL, DEFAULT_PORT, DOMAIN, MODEL_INPUTS

_LOGGER = logging.getLogger(__name__)


class HegelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Hegel amplifiers."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._model: str | None = None

    async def _async_try_connect(self, host: str) -> bool:
        """Try to connect to the Hegel amplifier using the library."""
        client = HegelClient(host, DEFAULT_PORT)
        try:
            await client.start()
            await client.ensure_connected(timeout=5.0)
        except HegelConnectionError, TimeoutError, OSError:
            return False
        else:
            return True
        finally:
            await client.stop()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            # Prevent duplicate entries by host
            self._async_abort_entries_match({CONF_HOST: host})

            if not await self._async_try_connect(host):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Hegel {user_input[CONF_MODEL]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_MODEL): vol.In(list(MODEL_INPUTS.keys())),
                }
            ),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery."""
        upnp = discovery_info.upnp or {}

        # Get host from presentationURL or ssdp_location
        url = upnp.get("presentationURL") or discovery_info.ssdp_location
        if not url:
            return self.async_abort(reason="no_host_found")

        host = URL(url).host
        if not host:
            return self.async_abort(reason="no_host_found")

        # Use UDN as unique id (device UUID)
        unique_id = discovery_info.ssdp_udn
        if not unique_id:
            return self.async_abort(reason="no_host_found")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Test connection before showing confirmation
        if not await self._async_try_connect(host):
            return self.async_abort(reason="cannot_connect")

        # Get device info
        friendly_name = upnp.get("friendlyName", f"Hegel {host}")
        suggested_model = upnp.get("modelName") or ""
        model_default = next(
            (m for m in MODEL_INPUTS if suggested_model.upper().startswith(m.upper())),
            None,
        )

        self._host = host
        self._name = friendly_name
        self._model = model_default

        self.context.update(
            {
                "title_placeholders": {"name": friendly_name},
            }
        )

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirmation - user can change model if needed."""
        assert self._host is not None
        assert self._name is not None

        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_HOST: self._host,
                    CONF_MODEL: user_input[CONF_MODEL],
                },
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
                        default=self._model or list(MODEL_INPUTS.keys())[0],
                    ): vol.In(list(MODEL_INPUTS.keys())),
                }
            ),
            description_placeholders={
                "host": self._host,
                "name": self._name,
            },
        )
