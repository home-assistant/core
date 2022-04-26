"""Config flow for DLNA DMS."""
from __future__ import annotations

import logging
from pprint import pformat
from typing import Any, cast
from urllib.parse import urlparse

from async_upnp_client.profiles.dlna import DmsDevice
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_URL
from homeassistant.data_entry_flow import AbortFlow, FlowResult

from .const import CONF_SOURCE_ID, CONFIG_VERSION, DEFAULT_NAME, DOMAIN
from .util import generate_source_id

LOGGER = logging.getLogger(__name__)


class DlnaDmsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a DLNA DMS config flow.

    The Unique Service Name (USN) of the DMS device is used as the unique_id for
    config entries and for entities. This USN may differ from the root USN if
    the DMS is an embedded device.
    """

    VERSION = CONFIG_VERSION

    def __init__(self) -> None:
        """Initialize flow."""
        self._discoveries: dict[str, ssdp.SsdpServiceInfo] = {}
        self._location: str | None = None
        self._usn: str | None = None
        self._name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user by listing unconfigured devices."""
        LOGGER.debug("async_step_user: user_input: %s", user_input)

        if user_input is not None and (host := user_input.get(CONF_HOST)):
            # User has chosen a device
            discovery = self._discoveries[host]
            await self._async_parse_discovery(discovery, raise_on_progress=False)
            return self._create_entry()

        if not (discoveries := await self._async_get_discoveries()):
            # Nothing found, abort configuration
            return self.async_abort(reason="no_devices_found")

        self._discoveries = {
            cast(str, urlparse(discovery.ssdp_location).hostname): discovery
            for discovery in discoveries
        }

        discovery_choices = {
            host: f"{discovery.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)} ({host})"
            for host, discovery in self._discoveries.items()
        }
        data_schema = vol.Schema({vol.Optional(CONF_HOST): vol.In(discovery_choices)})
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        LOGGER.debug("async_step_ssdp: discovery_info %s", pformat(discovery_info))

        await self._async_parse_discovery(discovery_info)

        # Abort if the device doesn't support all services required for a DmsDevice.
        # Use the discovery_info instead of DmsDevice.is_profile_device to avoid
        # contacting the device again.
        discovery_service_list = discovery_info.upnp.get(ssdp.ATTR_UPNP_SERVICE_LIST)
        if not discovery_service_list:
            return self.async_abort(reason="not_dms")

        services = discovery_service_list.get("service")
        if not services:
            discovery_service_ids: set[str] = set()
        elif isinstance(services, list):
            discovery_service_ids = {service.get("serviceId") for service in services}
        else:
            # Only one service defined (etree_to_dict failed to make a list)
            discovery_service_ids = {services.get("serviceId")}

        if not DmsDevice.SERVICE_IDS.issubset(discovery_service_ids):
            return self.async_abort(reason="not_dms")

        # Abort if another config entry has the same location, in case the
        # device doesn't have a static and unique UDN (breaking the UPnP spec).
        self._async_abort_entries_match({CONF_URL: self._location})

        self.context["title_placeholders"] = {"name": self._name}

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return self._create_entry()

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

    def _create_entry(self) -> FlowResult:
        """Create a config entry, assuming all required information is now known."""
        LOGGER.debug(
            "_create_entry: name: %s, location: %s, USN: %s",
            self._name,
            self._location,
            self._usn,
        )
        assert self._name
        assert self._location
        assert self._usn

        data = {
            CONF_URL: self._location,
            CONF_DEVICE_ID: self._usn,
            CONF_SOURCE_ID: generate_source_id(self.hass, self._name),
        }
        return self.async_create_entry(title=self._name, data=data)

    async def _async_parse_discovery(
        self, discovery_info: ssdp.SsdpServiceInfo, raise_on_progress: bool = True
    ) -> None:
        """Get required details from an SSDP discovery.

        Aborts if a device matching the SSDP USN has already been configured.
        """
        LOGGER.debug(
            "_async_parse_discovery: location: %s, USN: %s",
            discovery_info.ssdp_location,
            discovery_info.ssdp_usn,
        )

        if not discovery_info.ssdp_location or not discovery_info.ssdp_usn:
            raise AbortFlow("bad_ssdp")

        if not self._location:
            self._location = discovery_info.ssdp_location

        self._usn = discovery_info.ssdp_usn
        await self.async_set_unique_id(self._usn, raise_on_progress=raise_on_progress)

        # Abort if already configured, but update the last-known location
        self._abort_if_unique_id_configured(
            updates={CONF_URL: self._location}, reload_on_update=False
        )

        self._name = (
            discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or urlparse(self._location).hostname
            or DEFAULT_NAME
        )

    async def _async_get_discoveries(self) -> list[ssdp.SsdpServiceInfo]:
        """Get list of unconfigured DLNA devices discovered by SSDP."""
        # Get all compatible devices from ssdp's cache
        discoveries: list[ssdp.SsdpServiceInfo] = []
        for udn_st in DmsDevice.DEVICE_TYPES:
            st_discoveries = await ssdp.async_get_discovery_info_by_st(
                self.hass, udn_st
            )
            discoveries.extend(st_discoveries)

        # Filter out devices already configured
        current_unique_ids = {
            entry.unique_id
            for entry in self._async_current_entries(include_ignore=False)
        }
        discoveries = [
            disc for disc in discoveries if disc.ssdp_udn not in current_unique_ids
        ]

        return discoveries
