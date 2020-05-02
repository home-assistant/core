"""Config flow for UPNP."""
from typing import Mapping, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp

from .const import (  # pylint: disable=unused-import
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DISCOVERY_LOCATION,
    DISCOVERY_NAME,
    DISCOVERY_ST,
    DISCOVERY_UDN,
    DISCOVERY_USN,
    DOMAIN,
    LOGGER as _LOGGER,
)
from .device import Device


class UpnpFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UPnP/IGD config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    # Paths:
    # - ssdp(discovery_info) --> ssdp_confirm(None) --> ssdp_confirm({}) --> create_entry()
    # - user(None): scan --> user({...}) --> create_entry()
    # - import(None) --> create_entry()

    def __init__(self):
        """Initialize the UPnP/IGD config flow."""
        self._discoveries: Mapping = None

    async def async_step_user(self, user_input: Optional[Mapping] = None):
        """Handle a flow start."""
        _LOGGER.debug("async_step_user: user_input: %s", user_input)
        # This uses DISCOVERY_USN as the identifier for the device.

        if user_input is not None:
            # Ensure wanted device was discovered.
            matching_discoveries = [
                discovery
                for discovery in self._discoveries
                if discovery[DISCOVERY_USN] == user_input["usn"]
            ]
            if not matching_discoveries:
                return self.async_abort(reason="no_devices_discovered")

            discovery = matching_discoveries[0]
            await self.async_set_unique_id(
                discovery[DISCOVERY_USN], raise_on_progress=False
            )
            return await self._async_create_entry_from_data(discovery)

        # Discover devices.
        discoveries = await Device.async_discover(self.hass)

        # Store discoveries which have not been configured, add name for each discovery.
        current_usns = {entry.unique_id for entry in self._async_current_entries()}
        self._discoveries = [
            {
                **discovery,
                DISCOVERY_NAME: await self._async_get_name_for_discovery(discovery),
            }
            for discovery in discoveries
            if discovery[DISCOVERY_USN] not in current_usns
        ]

        # Ensure anything to add.
        if not self._discoveries:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required("usn"): vol.In(
                    {
                        discovery[DISCOVERY_USN]: discovery[DISCOVERY_NAME]
                        for discovery in self._discoveries
                    }
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema,)

    async def async_step_import(self, import_info: Optional[Mapping]):
        """Import a new UPnP/IGD device as a config entry.

        This flow is triggered by `async_setup`. If no device has been
        configured before, find any device and create a config_entry for it.
        Otherwise, do nothing.
        """
        _LOGGER.debug("async_step_import: import_info: %s", import_info)

        if import_info is None:
            # Landed here via configuration.yaml entry.
            # Any device already added, then abort.
            if self._async_current_entries():
                _LOGGER.debug("aborting, already configured")
                return self.async_abort(reason="already_configured")

        # Test if import_info isn't already configured.
        if import_info is not None and any(
            import_info["udn"] == entry.data[CONFIG_ENTRY_UDN]
            and import_info["st"] == entry.data[CONFIG_ENTRY_ST]
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")

        # Discover devices.
        self._discoveries = await Device.async_discover(self.hass)

        # Ensure anything to add. If not, silently abort.
        if not self._discoveries:
            _LOGGER.info("No UPnP devices discovered, aborting.")
            return self.async_abort(reason="no_devices_found")

        discovery = self._discoveries[0]
        return await self._async_create_entry_from_data(discovery)

    async def async_step_ssdp(self, discovery_info: Mapping):
        """Handle a discovered UPnP/IGD device.

        This flow is triggered by the SSDP component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        _LOGGER.debug("async_step_ssdp: discovery_info: %s", discovery_info)

        # Ensure not already configuring/configured.
        udn = discovery_info[ssdp.ATTR_UPNP_UDN]
        st = discovery_info[ssdp.ATTR_SSDP_ST]  # pylint: disable=invalid-name
        usn = f"{udn}::{st}"
        await self.async_set_unique_id(usn)
        self._abort_if_unique_id_configured()

        # Store discovery.
        name = discovery_info.get("friendlyName", "")
        discovery = {
            DISCOVERY_UDN: udn,
            DISCOVERY_ST: st,
            DISCOVERY_NAME: name,
        }
        self._discoveries = [discovery]

        # Ensure user recognizable.
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            "name": name,
        }

        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(self, user_input: Optional[Mapping] = None):
        """Confirm integration via SSDP."""
        _LOGGER.debug("async_step_ssdp_confirm: user_input: %s", user_input)
        if user_input is None:
            return self.async_show_form(step_id="ssdp_confirm")

        discovery = self._discoveries[0]
        return await self._async_create_entry_from_data(discovery)

    async def _async_create_entry_from_data(self, discovery: Mapping):
        """Create an entry from own _data."""
        _LOGGER.debug("_async_create_entry_from_data: discovery: %s", discovery)
        # Get name from device, if not found already.
        if DISCOVERY_NAME not in discovery and DISCOVERY_LOCATION in discovery:
            discovery[DISCOVERY_NAME] = await self._async_get_name_for_discovery(
                discovery
            )

        title = discovery.get(DISCOVERY_NAME, "")
        data = {
            CONFIG_ENTRY_UDN: discovery[DISCOVERY_UDN],
            CONFIG_ENTRY_ST: discovery[DISCOVERY_ST],
        }
        return self.async_create_entry(title=title, data=data)

    async def _async_get_name_for_discovery(self, discovery: Mapping):
        """Get the name of the device from a discovery."""
        _LOGGER.debug("_async_get_name_for_discovery: discovery: %s", discovery)
        device = await Device.async_create_device(
            self.hass, discovery[DISCOVERY_LOCATION]
        )
        return device.name
