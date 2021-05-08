"""Config flow for UPNP."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .const import (
    CONFIG_ENTRY_HOSTNAME,
    CONFIG_ENTRY_SCAN_INTERVAL,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DEFAULT_SCAN_INTERVAL,
    DISCOVERY_HOSTNAME,
    DISCOVERY_LOCATION,
    DISCOVERY_NAME,
    DISCOVERY_ST,
    DISCOVERY_UDN,
    DISCOVERY_UNIQUE_ID,
    DISCOVERY_USN,
    DOMAIN,
    DOMAIN_DEVICES,
    LOGGER as _LOGGER,
)
from .device import Device


def discovery_info_to_discovery(discovery_info: Mapping) -> Mapping:
    """Convert a SSDP-discovery to 'our' discovery."""
    return {
        DISCOVERY_UDN: discovery_info[ssdp.ATTR_UPNP_UDN],
        DISCOVERY_ST: discovery_info[ssdp.ATTR_SSDP_ST],
        DISCOVERY_LOCATION: discovery_info[ssdp.ATTR_SSDP_LOCATION],
        DISCOVERY_USN: discovery_info[ssdp.ATTR_SSDP_USN],
    }


class UpnpFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UPnP/IGD config flow."""

    VERSION = 1

    # Paths:
    # - ssdp(discovery_info) --> ssdp_confirm(None) --> ssdp_confirm({}) --> create_entry()
    # - user(None): scan --> user({...}) --> create_entry()
    # - import(None) --> create_entry()

    def __init__(self) -> None:
        """Initialize the UPnP/IGD config flow."""
        self._discoveries: Mapping = None

    async def async_step_user(
        self, user_input: Mapping | None = None
    ) -> Mapping[str, Any]:
        """Handle a flow start."""
        _LOGGER.debug("async_step_user: user_input: %s", user_input)

        if user_input is not None:
            # Ensure wanted device was discovered.
            matching_discoveries = [
                discovery
                for discovery in self._discoveries
                if discovery[DISCOVERY_UNIQUE_ID] == user_input["unique_id"]
            ]
            if not matching_discoveries:
                return self.async_abort(reason="no_devices_found")

            discovery = matching_discoveries[0]
            await self.async_set_unique_id(
                discovery[DISCOVERY_UNIQUE_ID], raise_on_progress=False
            )
            return await self._async_create_entry_from_discovery(discovery)

        # Discover devices.
        discoveries = [
            await Device.async_supplement_discovery(self.hass, discovery)
            for discovery in await Device.async_discover(self.hass)
        ]

        # Store discoveries which have not been configured.
        current_unique_ids = {
            entry.unique_id for entry in self._async_current_entries()
        }
        self._discoveries = [
            discovery
            for discovery in discoveries
            if discovery[DISCOVERY_UNIQUE_ID] not in current_unique_ids
        ]

        # Ensure anything to add.
        if not self._discoveries:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required("unique_id"): vol.In(
                    {
                        discovery[DISCOVERY_UNIQUE_ID]: discovery[DISCOVERY_NAME]
                        for discovery in self._discoveries
                    }
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    async def async_step_import(self, import_info: Mapping | None) -> Mapping[str, Any]:
        """Import a new UPnP/IGD device as a config entry.

        This flow is triggered by `async_setup`. If no device has been
        configured before, find any device and create a config_entry for it.
        Otherwise, do nothing.
        """
        _LOGGER.debug("async_step_import: import_info: %s", import_info)

        # Landed here via configuration.yaml entry.
        # Any device already added, then abort.
        if self._async_current_entries():
            _LOGGER.debug("Already configured, aborting")
            return self.async_abort(reason="already_configured")

        # Discover devices.
        self._discoveries = await Device.async_discover(self.hass)

        # Ensure anything to add. If not, silently abort.
        if not self._discoveries:
            _LOGGER.info("No UPnP devices discovered, aborting")
            return self.async_abort(reason="no_devices_found")

        # Ensure complete discovery.
        discovery = self._discoveries[0]
        if (
            DISCOVERY_UDN not in discovery
            or DISCOVERY_ST not in discovery
            or DISCOVERY_LOCATION not in discovery
            or DISCOVERY_USN not in discovery
        ):
            _LOGGER.debug("Incomplete discovery, ignoring")
            return self.async_abort(reason="incomplete_discovery")

        # Ensure not already configuring/configured.
        discovery = await Device.async_supplement_discovery(self.hass, discovery)
        unique_id = discovery[DISCOVERY_UNIQUE_ID]
        await self.async_set_unique_id(unique_id)

        return await self._async_create_entry_from_discovery(discovery)

    async def async_step_ssdp(self, discovery_info: Mapping) -> Mapping[str, Any]:
        """Handle a discovered UPnP/IGD device.

        This flow is triggered by the SSDP component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        _LOGGER.debug("async_step_ssdp: discovery_info: %s", discovery_info)

        # Ensure complete discovery.
        if (
            ssdp.ATTR_UPNP_UDN not in discovery_info
            or ssdp.ATTR_SSDP_ST not in discovery_info
            or ssdp.ATTR_SSDP_LOCATION not in discovery_info
            or ssdp.ATTR_SSDP_USN not in discovery_info
        ):
            _LOGGER.debug("Incomplete discovery, ignoring")
            return self.async_abort(reason="incomplete_discovery")

        # Convert to something we understand/speak.
        discovery = discovery_info_to_discovery(discovery_info)

        # Ensure not already configuring/configured.
        discovery = await Device.async_supplement_discovery(self.hass, discovery)
        unique_id = discovery[DISCOVERY_UNIQUE_ID]
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONFIG_ENTRY_HOSTNAME: discovery[DISCOVERY_HOSTNAME]}
        )

        # Handle devices changing their UDN, only allow a single
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        for config_entry in existing_entries:
            entry_hostname = config_entry.data.get(CONFIG_ENTRY_HOSTNAME)
            if entry_hostname == discovery[DISCOVERY_HOSTNAME]:
                _LOGGER.debug(
                    "Found existing config_entry with same hostname, discovery ignored"
                )
                return self.async_abort(reason="discovery_ignored")

        # Store discovery.
        self._discoveries = [discovery]

        # Ensure user recognizable.
        self.context["title_placeholders"] = {
            "name": discovery[DISCOVERY_NAME],
        }

        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(
        self, user_input: Mapping | None = None
    ) -> Mapping[str, Any]:
        """Confirm integration via SSDP."""
        _LOGGER.debug("async_step_ssdp_confirm: user_input: %s", user_input)
        if user_input is None:
            return self.async_show_form(step_id="ssdp_confirm")

        discovery = self._discoveries[0]
        return await self._async_create_entry_from_discovery(discovery)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Define the config flow to handle options."""
        return UpnpOptionsFlowHandler(config_entry)

    async def _async_create_entry_from_discovery(
        self,
        discovery: Mapping,
    ) -> Mapping[str, Any]:
        """Create an entry from discovery."""
        _LOGGER.debug(
            "_async_create_entry_from_discovery: discovery: %s",
            discovery,
        )

        title = discovery.get(DISCOVERY_NAME, "")
        data = {
            CONFIG_ENTRY_UDN: discovery[DISCOVERY_UDN],
            CONFIG_ENTRY_ST: discovery[DISCOVERY_ST],
            CONFIG_ENTRY_HOSTNAME: discovery[DISCOVERY_HOSTNAME],
        }
        return self.async_create_entry(title=title, data=data)


class UpnpOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a UPnP options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Mapping = None) -> None:
        """Manage the options."""
        if user_input is not None:
            udn = self.config_entry.data[CONFIG_ENTRY_UDN]
            coordinator = self.hass.data[DOMAIN][DOMAIN_DEVICES][udn].coordinator
            update_interval_sec = user_input.get(
                CONFIG_ENTRY_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            update_interval = timedelta(seconds=update_interval_sec)
            _LOGGER.debug("Updating coordinator, update_interval: %s", update_interval)
            coordinator.update_interval = update_interval
            return self.async_create_entry(title="", data=user_input)

        scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=scan_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=30)),
                }
            ),
        )
