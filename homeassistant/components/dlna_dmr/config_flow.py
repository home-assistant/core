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
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_TYPE,
    CONF_URL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import IntegrationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DEFAULT_NAME,
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
        self._discoveries: dict[str, Mapping[str, Any]] = {}
        self._location: str | None = None
        self._udn: str | None = None
        self._device_type: str | None = None
        self._name: str | None = None
        self._options: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Define the config flow to handle options."""
        return DlnaDmrOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: FlowInput = None) -> FlowResult:
        """Handle a flow initialized by the user.

        Let user choose from a list of found and unconfigured devices or to
        enter an URL manually.
        """
        LOGGER.debug("async_step_user: user_input: %s", user_input)

        if user_input is not None:
            if not (host := user_input.get(CONF_HOST)):
                # No device chosen, user might want to directly enter an URL
                return await self.async_step_manual()
            # User has chosen a device, ask for confirmation
            discovery = self._discoveries[host]
            await self._async_set_info_from_discovery(discovery)
            return self._create_entry()

        if not (discoveries := await self._async_get_discoveries()):
            # Nothing found, maybe the user knows an URL to try
            return await self.async_step_manual()

        self._discoveries = {
            discovery.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or urlparse(discovery[ssdp.ATTR_SSDP_LOCATION]).hostname: discovery
            for discovery in discoveries
        }

        data_schema = vol.Schema(
            {vol.Optional(CONF_HOST): vol.In(self._discoveries.keys())}
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_manual(self, user_input: FlowInput = None) -> FlowResult:
        """Manual URL entry by the user."""
        LOGGER.debug("async_step_manual: user_input: %s", user_input)

        # Device setup manually, assume we don't get SSDP broadcast notifications
        self._options[CONF_POLL_AVAILABILITY] = True

        errors = {}
        if user_input is not None:
            self._location = user_input[CONF_URL]
            try:
                await self._async_connect()
            except ConnectError as err:
                errors["base"] = err.args[0]
            else:
                return self._create_entry()

        data_schema = vol.Schema({CONF_URL: str})
        return self.async_show_form(
            step_id="manual", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_data: FlowInput = None) -> FlowResult:
        """Import a new DLNA DMR device from a config entry.

        This flow is triggered by `async_setup_platform`. If the device has not
        been migrated, and can be connected to, automatically import it. If it
        cannot be connected to, prompt the user to turn it on. If it has already
        been migrated, do nothing.
        """
        LOGGER.debug("async_step_import: import_data: %s", import_data)

        if not import_data or CONF_URL not in import_data:
            LOGGER.debug("Entry not imported: incomplete_config")
            return self.async_abort(reason="incomplete_config")

        self._location = import_data[CONF_URL]
        self._async_abort_entries_match({CONF_URL: self._location})

        # Use the location as this config flow's unique ID until UDN is known
        await self.async_set_unique_id(self._location)

        # Set options from the import_data, except listen_ip which is no longer used
        self._options[CONF_LISTEN_PORT] = import_data.get(CONF_LISTEN_PORT)
        self._options[CONF_CALLBACK_URL_OVERRIDE] = import_data.get(
            CONF_CALLBACK_URL_OVERRIDE
        )

        # Override device name if it's set in the YAML
        self._name = import_data.get(CONF_NAME)

        discoveries = await self._async_get_discoveries()

        # Find the device in the list of unconfigured devices
        for discovery in discoveries:
            if discovery[ssdp.ATTR_SSDP_LOCATION] == self._location:
                # Device found via SSDP, it shouldn't need polling
                self._options[CONF_POLL_AVAILABILITY] = False
                # Discovery info has everything required to create config entry
                await self._async_set_info_from_discovery(discovery)
                LOGGER.debug(
                    "Entry %s found via SSDP, with UDN %s",
                    self._location,
                    self._udn,
                )
                return self._create_entry()

        # This device will need to be polled
        self._options[CONF_POLL_AVAILABILITY] = True

        # Device was not found via SSDP, connect directly for configuration
        try:
            await self._async_connect()
        except ConnectError as err:
            # This will require user action
            LOGGER.debug("Entry %s not imported yet: %s", self._location, err.args[0])
            return await self.async_step_import_turn_on()

        LOGGER.debug("Entry %s ready for import", self._location)
        return self._create_entry()

    async def async_step_import_turn_on(
        self, user_input: FlowInput = None
    ) -> FlowResult:
        """Request the user to turn on the device so that import can finish."""
        LOGGER.debug("async_step_import_turn_on: %s", user_input)

        self.context["title_placeholders"] = {"name": self._name or self._location}

        errors = {}
        if user_input is not None:
            try:
                await self._async_connect()
            except ConnectError as err:
                errors["base"] = err.args[0]
            else:
                return self._create_entry()

        self._set_confirm_only()
        return self.async_show_form(step_id="import_turn_on", errors=errors)

    async def async_step_ssdp(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        LOGGER.debug("async_step_ssdp: discovery_info %s", pformat(discovery_info))

        await self._async_set_info_from_discovery(discovery_info)

        if _is_ignored_device(discovery_info):
            return self.async_abort(reason="alternative_integration")

        # Abort if the device doesn't support all services required for a DmrDevice.
        # Use the discovery_info instead of DmrDevice.is_profile_device to avoid
        # contacting the device again.
        discovery_service_list = discovery_info.get(ssdp.ATTR_UPNP_SERVICE_LIST)
        if not discovery_service_list:
            return self.async_abort(reason="not_dmr")
        discovery_service_ids = {
            service.get("serviceId")
            for service in discovery_service_list.get("service") or []
        }
        if not DmrDevice.SERVICE_IDS.issubset(discovery_service_ids):
            return self.async_abort(reason="not_dmr")

        # Abort if a migration flow for the device's location is in progress
        for progress in self._async_in_progress(include_uninitialized=True):
            if progress["context"].get("unique_id") == self._location:
                LOGGER.debug(
                    "Aborting SSDP setup because migration for %s is in progress",
                    self._location,
                )
                return self.async_abort(reason="already_in_progress")

        # Abort if another config entry has the same location, in case the
        # device doesn't have a static and unique UDN (breaking the UPnP spec).
        self._async_abort_entries_match({CONF_URL: self._location})

        self.context["title_placeholders"] = {"name": self._name}

        return await self.async_step_confirm()

    async def async_step_unignore(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Rediscover previously ignored devices by their unique_id."""
        LOGGER.debug("async_step_unignore: user_input: %s", user_input)
        self._udn = user_input["unique_id"]
        assert self._udn
        await self.async_set_unique_id(self._udn)

        # Find a discovery matching the unignored unique_id for a DMR device
        for dev_type in DmrDevice.DEVICE_TYPES:
            discovery = await ssdp.async_get_discovery_info_by_udn_st(
                self.hass, self._udn, dev_type
            )
            if discovery:
                break
        else:
            return self.async_abort(reason="discovery_error")

        await self._async_set_info_from_discovery(discovery, abort_if_configured=False)

        self.context["title_placeholders"] = {"name": self._name}

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: FlowInput = None) -> FlowResult:
        """Allow the user to confirm adding the device."""
        LOGGER.debug("async_step_confirm: %s", user_input)

        if user_input is not None:
            return self._create_entry()

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

    async def _async_connect(self) -> None:
        """Connect to a device to confirm it works and gather extra information.

        Updates this flow's unique ID to the device UDN if not already done.
        Raises ConnectError if something goes wrong.
        """
        LOGGER.debug("_async_connect: location: %s", self._location)
        assert self._location, "self._location has not been set before connect"

        domain_data = get_domain_data(self.hass)
        try:
            device = await domain_data.upnp_factory.async_create_device(self._location)
        except UpnpError as err:
            raise ConnectError("cannot_connect") from err

        if not DmrDevice.is_profile_device(device):
            raise ConnectError("not_dmr")

        device = find_device_of_type(device, DmrDevice.DEVICE_TYPES)

        if not self._udn:
            self._udn = device.udn
            await self.async_set_unique_id(self._udn)

        # Abort if already configured, but update the last-known location
        self._abort_if_unique_id_configured(
            updates={CONF_URL: self._location}, reload_on_update=False
        )

        if not self._device_type:
            self._device_type = device.device_type

        if not self._name:
            self._name = device.name

    def _create_entry(self) -> FlowResult:
        """Create a config entry, assuming all required information is now known."""
        LOGGER.debug(
            "_async_create_entry: location: %s, UDN: %s", self._location, self._udn
        )
        assert self._location
        assert self._udn
        assert self._device_type

        title = self._name or urlparse(self._location).hostname or DEFAULT_NAME
        data = {
            CONF_URL: self._location,
            CONF_DEVICE_ID: self._udn,
            CONF_TYPE: self._device_type,
        }
        return self.async_create_entry(title=title, data=data, options=self._options)

    async def _async_set_info_from_discovery(
        self, discovery_info: Mapping[str, Any], abort_if_configured: bool = True
    ) -> None:
        """Set information required for a config entry from the SSDP discovery."""
        LOGGER.debug(
            "_async_set_info_from_discovery: location: %s, UDN: %s",
            discovery_info[ssdp.ATTR_SSDP_LOCATION],
            discovery_info[ssdp.ATTR_SSDP_UDN],
        )

        if not self._location:
            self._location = discovery_info[ssdp.ATTR_SSDP_LOCATION]
            assert isinstance(self._location, str)

        self._udn = discovery_info[ssdp.ATTR_SSDP_UDN]
        await self.async_set_unique_id(self._udn)

        if abort_if_configured:
            # Abort if already configured, but update the last-known location
            self._abort_if_unique_id_configured(
                updates={CONF_URL: self._location}, reload_on_update=False
            )

        self._device_type = (
            discovery_info.get(ssdp.ATTR_SSDP_NT) or discovery_info[ssdp.ATTR_SSDP_ST]
        )
        self._name = (
            discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or urlparse(self._location).hostname
            or DEFAULT_NAME
        )

    async def _async_get_discoveries(self) -> list[Mapping[str, Any]]:
        """Get list of unconfigured DLNA devices discovered by SSDP."""
        LOGGER.debug("_get_discoveries")

        # Get all compatible devices from ssdp's cache
        discoveries: list[Mapping[str, Any]] = []
        for udn_st in DmrDevice.DEVICE_TYPES:
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
            disc
            for disc in discoveries
            if disc[ssdp.ATTR_SSDP_UDN] not in current_unique_ids
        ]

        return discoveries


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
            if (suggested_value := options.get(key)) is None:
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


def _is_ignored_device(discovery_info: Mapping[str, Any]) -> bool:
    """Return True if this device should be ignored for discovery.

    These devices are supported better by other integrations, so don't bug
    the user about them. The user can add them if desired by via the user config
    flow, which will list all discovered but unconfigured devices.
    """
    # Did the discovery trigger more than just this flow?
    if len(discovery_info.get(ssdp.ATTR_HA_MATCHING_DOMAINS, set())) > 1:
        LOGGER.debug(
            "Ignoring device supported by multiple integrations: %s",
            discovery_info[ssdp.ATTR_HA_MATCHING_DOMAINS],
        )
        return True

    # Is the root device not a DMR?
    if discovery_info.get(ssdp.ATTR_UPNP_DEVICE_TYPE) not in DmrDevice.DEVICE_TYPES:
        return True

    # Special cases for devices with other discovery methods (e.g. mDNS), or
    # that advertise multiple unrelated (sent in separate discovery packets)
    # UPnP devices.
    manufacturer = discovery_info.get(ssdp.ATTR_UPNP_MANUFACTURER, "").lower()
    model = discovery_info.get(ssdp.ATTR_UPNP_MODEL_NAME, "").lower()

    if manufacturer.startswith("xbmc") or model == "kodi":
        # kodi
        return True
    if "philips" in manufacturer and "tv" in model:
        # philips_js
        # These TVs don't have a stable UDN, so also get discovered as a new
        # device every time they are turned on.
        return True
    if manufacturer.startswith("samsung") and "tv" in model:
        # samsungtv
        return True
    if manufacturer.startswith("lg") and "tv" in model:
        # webostv
        return True

    return False
