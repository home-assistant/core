"""Configuration flow for Prana integration discovered via Zeroconf.

The flow is discovery-only. Users confirm a found device; manual starts abort.
"""

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_CONFIG, CONF_MDNS, DOMAIN

SERVICE_TYPE = "_prana._tcp.local."

_LOGGER = logging.getLogger(__name__)


class PranaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Prana config flow."""

    def __init__(self) -> None:
        """Initialize the Prana config flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._config: dict | str | None = None
        self._mdns: str | None = None
        self.context = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery of a Prana device."""
        _LOGGER.debug("Discovered device via Zeroconf: %s", discovery_info)

        name = discovery_info.name
        host = discovery_info.host
        # Set unique_id to the mDNS name to prevent duplicate entries, name is unique per each device
        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured()

        raw_config = discovery_info.properties
        friendly_name = discovery_info.properties.get("label", "")

        self.context["title_placeholders"] = {"name": friendly_name}

        self._host = host
        self._name = friendly_name
        self._config = raw_config
        self._mdns = name

        discovered: dict = self.hass.data.setdefault(f"{DOMAIN}_discovered", {})
        discovered[name] = {
            "host": host,
            "label": friendly_name or name,
            "properties": raw_config,
        }

        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow user to pick from discovered devices and configure one."""
        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual entry by IP address."""
        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input.get(CONF_NAME) or host

            self._async_abort_entries_match({CONF_HOST: host})

            self._host = host
            self._name = name
            self._config = None
            self._mdns = None
            return self.async_create_entry(
                title=cast(str, self._name),
                data={
                    CONF_NAME: cast(str, self._name),
                    CONF_HOST: cast(str, self._host),
                    CONF_CONFIG: self._config,
                    CONF_MDNS: self._mdns,
                },
                options={},
                description_placeholders={
                    "name": cast(str, self._name),
                    "host": cast(str, self._host),
                },
            )

        schema = vol.Schema(
            {vol.Required(CONF_HOST): str, vol.Optional(CONF_NAME): str}
        )
        return self.async_show_form(step_id="manual", data_schema=schema)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show confirmation form or create entry when submitted."""
        if not all([self._host, self._name, self._mdns]):
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            return self.async_create_entry(
                title=cast(str, self._name),
                data={
                    CONF_NAME: cast(str, self._name),
                    CONF_HOST: cast(str, self._host),
                    CONF_CONFIG: self._config,
                    CONF_MDNS: self._mdns,
                },
                options={},
                description_placeholders={
                    "name": cast(str, self._name),
                    "host": cast(str, self._host),
                },
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": cast(str, self._name),
                "host": cast(str, self._host),
            },
        )
