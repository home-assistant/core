"""Config flow for UPNP."""
from typing import Mapping, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp

from .const import (  # pylint: disable=unused-import
    DOMAIN,
    LOGGER as _LOGGER,
)
from .device import Device
from urllib.parse import urlparse


LOCATION = "location"
NAME = "name"
ST = "st"
UDN = "udn"


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
        self._data: Mapping = None
        self._discoveries: Mapping = None

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        _LOGGER.debug("async_step_user: user_input: %s", user_input)

        if user_input is not None:
            # Ensure wanted device was discovered.
            matching_discoveries = [
                discovery
                for discovery in self._discoveries
                if discovery["unique_id"] == user_input["unique_id"]
            ]
            if not matching_discoveries:
                errors = {"base": "no_devices_discovered"}
                return self.async_show_form(step_id="user", errors=errors,)

            # Title/name will be updated later on.
            self._data = matching_discoveries[0]
            self._data[NAME] = urlparse(self._data[ssdp.ATTR_SSDP_LOCATION]).hostname
            return self._async_create_entry_from_data()

        # Discover devices.
        self._discoveries = await Device.async_discover(self.hass)

        # Filter discoveries which are already configured.
        current_unique_ids = [
            entry.unique_id for entry in self._async_current_entries()
        ]
        self._discoveries = [
            discovery
            for discovery in self._discoveries
            if discovery["unique_id"] not in current_unique_ids
        ]

        # Ensure anything to add.
        if not self._discoveries:
            errors = {"base": "no_devices_discovered"}
            return self.async_show_form(step_id="user", errors=errors,)

        data_schema = vol.Schema(
            {
                vol.Required("unique_id"): vol.In(
                    {
                        discovery["unique_id"]: urlparse(
                            discovery[ssdp.ATTR_SSDP_LOCATION]
                        ).hostname
                        for discovery in self._discoveries
                    }
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema,)

    async def async_step_import(self, import_info: Optional[Mapping]):
        """Import a new UPnP/IGD device as a config entry.

        This flow is triggered by `async_setup`.
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
            import_info["udn"] == entry.data["udn"]
            and import_info["st"] == entry.data["st"]
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")

        # Discover devices.
        self._discoveries = await Device.async_discover(self.hass)

        # Ensure anything to add. If not, silently abort.
        if not self._discoveries:
            _LOGGER.info("No UPnP devices discovered, aborting.")
            return self.async_abort(reason="no_devices_found")

        # Create new config_entry.
        self._data = self._discoveries[0]
        return self._async_create_entry_from_data()

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
        self._abort_if_unique_id_configured(updates={UDN: udn, ST: st})

        # Store discovery.
        name = discovery_info.get("friendlyName", "")
        self._data = {
            UDN: udn,
            ST: st,
            NAME: name,
        }

        # Ensure user recognizable.
        location = discovery_info[ssdp.ATTR_SSDP_LOCATION]
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            "name": name,
            "host": urlparse(location).hostname,
        }

        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(self, user_input=None):
        """Confirm integration via SSDP."""
        _LOGGER.debug("async_step_ssdp_confirm: user_input: %s", user_input)
        if user_input is None:
            return self.async_show_form(step_id="ssdp_confirm")

        return self._async_create_entry_from_data()

    def _async_create_entry_from_data(self):
        """Create an entry from own _data."""
        title = self._data["name"]
        data = {
            UDN: self._data["udn"],
            ST: self._data["st"],
        }
        return self.async_create_entry(title=title, data=data)
