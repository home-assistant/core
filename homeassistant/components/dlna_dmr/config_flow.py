"""Config flow for DLNA DMR."""
from __future__ import annotations

from collections.abc import Callable
import logging
from pprint import pformat
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from async_upnp_client.client import UpnpError
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.profiles.profile import find_device_of_type
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME, CONF_TYPE, CONF_URL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import IntegrationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN,
)
from .data import get_domain_data

LOGGER = logging.getLogger(__name__)

FlowInput = Optional[Mapping[str, Any]]


class ConnectError(IntegrationError):
    """Error occurred when trying to connect to a device."""


class DlnaDmrFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a DLNA DMR config flow.

    The Unique Device Name (UDN) of the DMR device is used as the unique_id for
    config entries and for entities. This UDN may differ from the root UDN if
    the DMR is an embedded device.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._discoveries: list[Mapping[str, str]] = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Define the config flow to handle options."""
        return DlnaDmrOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: FlowInput = None) -> FlowResult:
        """Handle a flow initialized by the user: manual URL entry.

        Discovered devices will already be displayed, no need to prompt user
        with them here.
        """
        LOGGER.debug("async_step_user: user_input: %s", user_input)

        errors = {}
        if user_input is not None:
            try:
                discovery = await self._async_connect(user_input[CONF_URL])
            except ConnectError as err:
                errors["base"] = err.args[0]
            else:
                # If unmigrated config was imported earlier then use it
                import_data = get_domain_data(self.hass).unmigrated_config.get(
                    user_input[CONF_URL]
                )
                if import_data is not None:
                    return await self.async_step_import(import_data)
                # Device setup manually, assume we don't get SSDP broadcast notifications
                options = {CONF_POLL_AVAILABILITY: True}
                return await self._async_create_entry_from_discovery(discovery, options)

        data_schema = vol.Schema({CONF_URL: str})
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_data: FlowInput = None) -> FlowResult:
        """Import a new DLNA DMR device from a config entry.

        This flow is triggered by `async_setup`. If no device has been
        configured before, find any matching device and create a config_entry
        for it. Otherwise, do nothing.
        """
        LOGGER.debug("async_step_import: import_data: %s", import_data)

        if not import_data or CONF_URL not in import_data:
            LOGGER.debug("Entry not imported: incomplete_config")
            return self.async_abort(reason="incomplete_config")

        self._async_abort_entries_match({CONF_URL: import_data[CONF_URL]})

        location = import_data[CONF_URL]
        self._discoveries = await self._async_get_discoveries()

        poll_availability = True

        # Find the device in the list of unconfigured devices
        for discovery in self._discoveries:
            if discovery[ssdp.ATTR_SSDP_LOCATION] == location:
                # Device found via SSDP, it shouldn't need polling
                poll_availability = False
                LOGGER.debug(
                    "Entry %s found via SSDP, with UDN %s",
                    import_data[CONF_URL],
                    discovery[ssdp.ATTR_SSDP_UDN],
                )
                break
        else:
            # Not in discoveries. Try connecting directly.
            try:
                discovery = await self._async_connect(location)
            except ConnectError as err:
                LOGGER.debug(
                    "Entry %s not imported: %s", import_data[CONF_URL], err.args[0]
                )
                # Store the config to apply if the device is added later
                get_domain_data(self.hass).unmigrated_config[location] = import_data
                return self.async_abort(reason=err.args[0])

        # Set options from the import_data, except listen_ip which is no longer used
        options = {
            CONF_LISTEN_PORT: import_data.get(CONF_LISTEN_PORT),
            CONF_CALLBACK_URL_OVERRIDE: import_data.get(CONF_CALLBACK_URL_OVERRIDE),
            CONF_POLL_AVAILABILITY: poll_availability,
        }

        # Override device name if it's set in the YAML
        if CONF_NAME in import_data:
            discovery = dict(discovery)
            discovery[ssdp.ATTR_UPNP_FRIENDLY_NAME] = import_data[CONF_NAME]

        LOGGER.debug("Entry %s ready for import", import_data[CONF_URL])
        return await self._async_create_entry_from_discovery(discovery, options)

    async def async_step_ssdp(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        LOGGER.debug("async_step_ssdp: discovery_info %s", pformat(discovery_info))

        self._discoveries = [discovery_info]

        udn = discovery_info[ssdp.ATTR_SSDP_UDN]
        location = discovery_info[ssdp.ATTR_SSDP_LOCATION]

        # Abort if already configured, but update the last-known location
        await self.async_set_unique_id(udn)
        self._abort_if_unique_id_configured(
            updates={CONF_URL: location}, reload_on_update=False
        )

        # If the device needs migration because it wasn't turned on when HA
        # started, silently migrate it now.
        import_data = get_domain_data(self.hass).unmigrated_config.get(location)
        if import_data is not None:
            return await self.async_step_import(import_data)

        parsed_url = urlparse(location)
        name = discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME) or parsed_url.hostname
        self.context["title_placeholders"] = {"name": name}

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: FlowInput = None) -> FlowResult:
        """Allow the user to confirm adding the device.

        Also check that the device is still available, otherwise when it is
        added to HA it won't report the correct DeviceInfo.
        """
        LOGGER.debug("async_step_confirm: %s", user_input)

        errors = {}
        if user_input is not None:
            discovery = self._discoveries[0]
            try:
                await self._async_connect(discovery[ssdp.ATTR_SSDP_LOCATION])
            except ConnectError as err:
                errors["base"] = err.args[0]
            else:
                return await self._async_create_entry_from_discovery(discovery)

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm", errors=errors)

    async def _async_create_entry_from_discovery(
        self,
        discovery: Mapping[str, Any],
        options: Mapping[str, Any] | None = None,
    ) -> FlowResult:
        """Create an entry from discovery."""
        LOGGER.debug("_async_create_entry_from_discovery: discovery: %s", discovery)

        location = discovery[ssdp.ATTR_SSDP_LOCATION]
        udn = discovery[ssdp.ATTR_SSDP_UDN]

        # Abort if already configured, but update the last-known location
        await self.async_set_unique_id(udn)
        self._abort_if_unique_id_configured(updates={CONF_URL: location})

        parsed_url = urlparse(location)
        title = discovery.get(ssdp.ATTR_UPNP_FRIENDLY_NAME) or parsed_url.hostname

        data = {
            CONF_URL: discovery[ssdp.ATTR_SSDP_LOCATION],
            CONF_DEVICE_ID: discovery[ssdp.ATTR_SSDP_UDN],
            CONF_TYPE: discovery.get(ssdp.ATTR_SSDP_NT) or discovery[ssdp.ATTR_SSDP_ST],
        }
        return self.async_create_entry(title=title, data=data, options=options)

    async def _async_get_discoveries(self) -> list[Mapping[str, str]]:
        """Get list of unconfigured DLNA devices discovered by SSDP."""
        LOGGER.debug("_get_discoveries")

        # Get all compatible devices from ssdp's cache
        discoveries: list[Mapping[str, str]] = []
        for udn_st in DmrDevice.DEVICE_TYPES:
            st_discoveries = await ssdp.async_get_discovery_info_by_st(
                self.hass, udn_st
            )
            discoveries.extend(st_discoveries)

        # Filter out devices already configured
        current_unique_ids = {
            entry.unique_id for entry in self._async_current_entries()
        }
        discoveries = [
            disc
            for disc in discoveries
            if disc[ssdp.ATTR_SSDP_UDN] not in current_unique_ids
        ]

        return discoveries

    async def _async_connect(self, location: str) -> dict[str, str]:
        """Connect to a device to confirm it works and get discovery information.

        Raises ConnectError if something goes wrong.
        """
        LOGGER.debug("_async_connect(location=%s)", location)
        domain_data = get_domain_data(self.hass)
        try:
            device = await domain_data.upnp_factory.async_create_device(location)
        except UpnpError as err:
            raise ConnectError("could_not_connect") from err

        try:
            device = find_device_of_type(device, DmrDevice.DEVICE_TYPES)
        except UpnpError as err:
            raise ConnectError("not_dmr") from err

        discovery = {
            ssdp.ATTR_SSDP_LOCATION: location,
            ssdp.ATTR_SSDP_UDN: device.udn,
            ssdp.ATTR_SSDP_ST: device.device_type,
            ssdp.ATTR_UPNP_FRIENDLY_NAME: device.name,
        }

        return discovery


class DlnaDmrOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a DLNA DMR options flow.

    Configures the single instance and updates the existing config entry.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        # Don't modify existing (read-only) options -- copy and update instead
        options = dict(self.config_entry.options)

        if user_input is not None:
            LOGGER.debug("user_input: %s", user_input)
            listen_port = user_input.get(CONF_LISTEN_PORT) or None
            callback_url_override = user_input.get(CONF_CALLBACK_URL_OVERRIDE) or None

            try:
                # Cannot use cv.url validation in the schema itself so apply
                # extra validation here
                if callback_url_override:
                    cv.url(callback_url_override)
            except vol.Invalid:
                errors["base"] = "invalid_url"

            options[CONF_LISTEN_PORT] = listen_port
            options[CONF_CALLBACK_URL_OVERRIDE] = callback_url_override
            options[CONF_POLL_AVAILABILITY] = user_input[CONF_POLL_AVAILABILITY]

            # Save if there's no errors, else fall through and show the form again
            if not errors:
                return self.async_create_entry(title="", data=options)

        fields = {}

        def _add_with_suggestion(key: str, validator: Callable) -> None:
            """Add a field to with a suggested, not default, value."""
            suggested_value = options.get(key)
            if suggested_value is None:
                fields[vol.Optional(key)] = validator
            else:
                fields[
                    vol.Optional(key, description={"suggested_value": suggested_value})
                ] = validator

        # listen_port can be blank or 0 for "bind any free port"
        _add_with_suggestion(CONF_LISTEN_PORT, cv.port)
        _add_with_suggestion(CONF_CALLBACK_URL_OVERRIDE, str)
        fields[
            vol.Required(
                CONF_POLL_AVAILABILITY,
                default=options.get(CONF_POLL_AVAILABILITY, False),
            )
        ] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
            errors=errors,
        )
