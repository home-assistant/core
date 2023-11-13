"""Config flow for UPNP."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.ssdp import SsdpServiceInfo
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONFIG_ENTRY_HOST,
    CONFIG_ENTRY_LOCATION,
    CONFIG_ENTRY_MAC_ADDRESS,
    CONFIG_ENTRY_ORIGINAL_UDN,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
    DOMAIN_DISCOVERIES,
    LOGGER,
    ST_IGD_V1,
    ST_IGD_V2,
)
from .device import async_get_mac_address_from_host, get_preferred_location


def _friendly_name_from_discovery(discovery_info: ssdp.SsdpServiceInfo) -> str:
    """Extract user-friendly name from discovery."""
    return cast(
        str,
        discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
        or discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME)
        or discovery_info.ssdp_headers.get("_host", ""),
    )


def _is_complete_discovery(discovery_info: ssdp.SsdpServiceInfo) -> bool:
    """Test if discovery is complete and usable."""
    return bool(
        ssdp.ATTR_UPNP_UDN in discovery_info.upnp
        and discovery_info.ssdp_st
        and discovery_info.ssdp_all_locations
        and discovery_info.ssdp_usn
    )


async def _async_discovered_igd_devices(
    hass: HomeAssistant,
) -> list[ssdp.SsdpServiceInfo]:
    """Discovery IGD devices."""
    return await ssdp.async_get_discovery_info_by_st(
        hass, ST_IGD_V1
    ) + await ssdp.async_get_discovery_info_by_st(hass, ST_IGD_V2)


async def _async_mac_address_from_discovery(
    hass: HomeAssistant, discovery: SsdpServiceInfo
) -> str | None:
    """Get the mac address from a discovery."""
    location = get_preferred_location(discovery.ssdp_all_locations)
    host = urlparse(location).hostname
    assert host is not None
    return await async_get_mac_address_from_host(hass, host)


def _is_igd_device(discovery_info: ssdp.SsdpServiceInfo) -> bool:
    """Test if discovery is a complete IGD device."""
    root_device_info = discovery_info.upnp
    return root_device_info.get(ssdp.ATTR_UPNP_DEVICE_TYPE) in {ST_IGD_V1, ST_IGD_V2}


class UpnpFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UPnP/IGD config flow."""

    VERSION = 1

    # Paths:
    # - ssdp(discovery_info) --> ssdp_confirm(None)
    # --> ssdp_confirm({}) --> create_entry()
    # - user(None): scan --> user({...}) --> create_entry()

    @property
    def _discoveries(self) -> dict[str, SsdpServiceInfo]:
        """Get current discoveries."""
        domain_data: dict = self.hass.data.setdefault(DOMAIN, {})
        return domain_data.setdefault(DOMAIN_DISCOVERIES, {})

    def _add_discovery(self, discovery: SsdpServiceInfo) -> None:
        """Add a discovery."""
        self._discoveries[discovery.ssdp_usn] = discovery

    def _remove_discovery(self, usn: str) -> SsdpServiceInfo:
        """Remove a discovery by its USN/unique_id."""
        return self._discoveries.pop(usn)

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow start."""
        LOGGER.debug("async_step_user: user_input: %s", user_input)

        if user_input is not None:
            # Ensure wanted device was discovered.
            assert self._discoveries
            discovery = next(
                iter(
                    discovery
                    for discovery in self._discoveries.values()
                    if discovery.ssdp_usn == user_input["unique_id"]
                )
            )
            await self.async_set_unique_id(discovery.ssdp_usn, raise_on_progress=False)
            return await self._async_create_entry_from_discovery(discovery)

        # Discover devices.
        discoveries = await _async_discovered_igd_devices(self.hass)

        # Store discoveries which have not been configured.
        current_unique_ids = {
            entry.unique_id for entry in self._async_current_entries()
        }
        for discovery in discoveries:
            if (
                _is_complete_discovery(discovery)
                and _is_igd_device(discovery)
                and discovery.ssdp_usn not in current_unique_ids
            ):
                self._add_discovery(discovery)

        # Ensure anything to add.
        if not self._discoveries:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required("unique_id"): vol.In(
                    {
                        discovery.ssdp_usn: _friendly_name_from_discovery(discovery)
                        for discovery in self._discoveries.values()
                    }
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a discovered UPnP/IGD device.

        This flow is triggered by the SSDP component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        LOGGER.debug("async_step_ssdp: discovery_info: %s", discovery_info)

        # Ensure complete discovery.
        if not _is_complete_discovery(discovery_info):
            LOGGER.debug("Incomplete discovery, ignoring")
            return self.async_abort(reason="incomplete_discovery")

        # Ensure device is usable. Ideally we would use IgdDevice.is_profile_device,
        # but that requires constructing the device completely.
        if not _is_igd_device(discovery_info):
            LOGGER.debug("Non IGD device, ignoring")
            return self.async_abort(reason="non_igd_device")

        # Ensure not already configuring/configured.
        unique_id = discovery_info.ssdp_usn
        await self.async_set_unique_id(unique_id)
        mac_address = await _async_mac_address_from_discovery(self.hass, discovery_info)
        host = discovery_info.ssdp_headers["_host"]
        self._abort_if_unique_id_configured(
            # Store mac address and other data for older entries.
            # The location is stored in the config entry such that
            # when the location changes, the entry is reloaded.
            updates={
                CONFIG_ENTRY_MAC_ADDRESS: mac_address,
                CONFIG_ENTRY_LOCATION: get_preferred_location(
                    discovery_info.ssdp_all_locations
                ),
                CONFIG_ENTRY_HOST: host,
                CONFIG_ENTRY_ST: discovery_info.ssdp_st,
            },
        )

        # Handle devices changing their UDN, only allow a single host.
        for entry in self._async_current_entries(include_ignore=True):
            entry_mac_address = entry.data.get(CONFIG_ENTRY_MAC_ADDRESS)
            entry_host = entry.data.get(CONFIG_ENTRY_HOST)
            if entry_mac_address != mac_address and entry_host != host:
                continue

            entry_st = entry.data.get(CONFIG_ENTRY_ST)
            if discovery_info.ssdp_st != entry_st:
                # Check ssdp_st to prevent swapping between IGDv1 and IGDv2.
                continue

            if entry.source == config_entries.SOURCE_IGNORE:
                # Host was already ignored. Don't update ignored entries.
                return self.async_abort(reason="discovery_ignored")

            LOGGER.debug("Updating entry: %s", entry.entry_id)
            self.hass.config_entries.async_update_entry(
                entry,
                unique_id=unique_id,
                data={**entry.data, CONFIG_ENTRY_UDN: discovery_info.ssdp_udn},
            )
            if entry.state == config_entries.ConfigEntryState.LOADED:
                # Only reload when entry has state LOADED; when entry has state
                # SETUP_RETRY, another load is started,
                # causing the entry to be loaded twice.
                LOGGER.debug("Reloading entry: %s", entry.entry_id)
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
            return self.async_abort(reason="config_entry_updated")

        # Store discovery.
        self._add_discovery(discovery_info)

        # Ensure user recognizable.
        self.context["title_placeholders"] = {
            "name": _friendly_name_from_discovery(discovery_info),
        }

        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Confirm integration via SSDP."""
        LOGGER.debug("async_step_ssdp_confirm: user_input: %s", user_input)
        if user_input is None:
            return self.async_show_form(step_id="ssdp_confirm")

        assert self.unique_id
        discovery = self._remove_discovery(self.unique_id)
        return await self._async_create_entry_from_discovery(discovery)

    async def async_step_ignore(self, user_input: dict[str, Any]) -> FlowResult:
        """Ignore this config flow."""
        usn = user_input["unique_id"]
        discovery = self._remove_discovery(usn)
        mac_address = await _async_mac_address_from_discovery(self.hass, discovery)
        data = {
            CONFIG_ENTRY_UDN: discovery.upnp[ssdp.ATTR_UPNP_UDN],
            CONFIG_ENTRY_ST: discovery.ssdp_st,
            CONFIG_ENTRY_ORIGINAL_UDN: discovery.upnp[ssdp.ATTR_UPNP_UDN],
            CONFIG_ENTRY_MAC_ADDRESS: mac_address,
            CONFIG_ENTRY_HOST: discovery.ssdp_headers["_host"],
            CONFIG_ENTRY_LOCATION: get_preferred_location(discovery.ssdp_all_locations),
        }

        await self.async_set_unique_id(user_input["unique_id"], raise_on_progress=False)
        return self.async_create_entry(title=user_input["title"], data=data)

    async def _async_create_entry_from_discovery(
        self,
        discovery: SsdpServiceInfo,
    ) -> FlowResult:
        """Create an entry from discovery."""
        LOGGER.debug(
            "_async_create_entry_from_discovery: discovery: %s",
            discovery,
        )

        title = _friendly_name_from_discovery(discovery)
        mac_address = await _async_mac_address_from_discovery(self.hass, discovery)
        data = {
            CONFIG_ENTRY_UDN: discovery.upnp[ssdp.ATTR_UPNP_UDN],
            CONFIG_ENTRY_ST: discovery.ssdp_st,
            CONFIG_ENTRY_ORIGINAL_UDN: discovery.upnp[ssdp.ATTR_UPNP_UDN],
            CONFIG_ENTRY_LOCATION: get_preferred_location(discovery.ssdp_all_locations),
            CONFIG_ENTRY_MAC_ADDRESS: mac_address,
            CONFIG_ENTRY_HOST: discovery.ssdp_headers["_host"],
        }
        return self.async_create_entry(title=title, data=data)
