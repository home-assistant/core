"""Configuration flow for Prana integration discovered via Zeroconf.

The flow is discovery-only. Users confirm a found device; manual starts abort.
"""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_CONFIG, CONF_MDNS, DOMAIN

SERVICE_TYPE = "_prana._tcp.local."

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Prana config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Prana config flow."""
        # Store a single discovered device for this flow (one flow per device)
        self._host: str | None = None
        self._name: str | None = None
        self._config: dict | str | None = None
        self._mdns: str | None = None
        # Ensure we have a mutable context mapping (tests may call async_set_unique_id)
        # `config_entries` may provide a mappingproxy in some test harnesses
        self.context = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery of a Prana device."""
        _LOGGER.debug("Discovered device via Zeroconf: %s", discovery_info)

        if discovery_info.type != SERVICE_TYPE:
            return self.async_abort(reason="not_prana_device")

        name = discovery_info.name
        # Context mutation not required; keep existing mapping

        # If an entry with the same unique_id (mdns name) already exists, abort
        # This ensures duplicate devices are not configured twice
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == name:
                return self.async_abort(reason="already_configured")

        # Prefer the resolved IP address fields provided by ZeroconfServiceInfo
        # Tests provide `ip_address` / `ip_addresses`, so use those first,
        # with fallbacks to `host` or `hostname`
        host = (
            getattr(discovery_info, "ip_address", None)
            or (
                discovery_info.ip_addresses[0]
                if getattr(discovery_info, "ip_addresses", None)
                else None
            )
            or getattr(discovery_info, "host", None)
            or getattr(discovery_info, "hostname", None)
        )
        if host is not None:
            host = str(host)

        # Set a stable unique ID so the discovery card can offer "Ignore"
        await self.async_set_unique_id(name)
        # If already configured, abort (prevent duplicate configuration)
        self._abort_if_unique_id_configured()

        # Extract friendly name from the config blob
        raw_config = discovery_info.properties
        friendly_name = discovery_info.properties.get("label", "")

        # Set placeholders so the discovery card subtitle shows device name
        self.context["title_placeholders"] = {"name": friendly_name}

        # Keep details for confirm step
        self._host = host
        self._name = friendly_name
        self._config = raw_config
        self._mdns = name

        # Persist discovered device metadata so user-start flow can list devices
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
        """Allow user to pick from discovered devices and configure one.

        If no devices were discovered, abort with no_devices_found.
        """
        discovered: dict = self.hass.data.get(f"{DOMAIN}_discovered", {})
        if not discovered:
            return self.async_abort(reason="no_devices_found")

        # Build choices: mdns -> label
        choices = {mdns: info.get("label", mdns) for mdns, info in discovered.items()}

        if user_input is not None:
            mdns = user_input["mdns"]
            info = discovered.get(mdns)
            if not info:
                return self.async_abort(reason="no_devices_found")

            # Populate internal fields and create entry (same as confirm)
            self._host = info.get("host")
            self._name = info.get("label")
            self._config = info.get("properties")
            self._mdns = mdns

            # Ensure unique id and prevent duplicates
            await self.async_set_unique_id(mdns)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._name or "Prana",
                data={
                    CONF_NAME: self._name,
                    CONF_HOST: self._host,
                    CONF_CONFIG: self._config,
                    CONF_MDNS: self._mdns,
                },
                options={},
                description_placeholders={},
            )

        schema = vol.Schema({"mdns": vol.In(choices)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show confirmation form or create entry when submitted."""
        # Safety: ensure we have discovery data
        if not all([self._host, self._name, self._mdns]):
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            return self.async_create_entry(
                title=self._name or "Prana",
                data={
                    CONF_NAME: self._name,
                    CONF_HOST: self._host,
                    CONF_CONFIG: self._config,
                    CONF_MDNS: self._mdns,
                },
                options={},
                description_placeholders={},
            )

        # Empty form -> shows only a Submit button
        return self.async_show_form(step_id="confirm")
