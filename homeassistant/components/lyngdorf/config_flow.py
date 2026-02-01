"""Config flow for Lyngdorf Integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlparse

from async_upnp_client.profiles.dlna import DmrDevice
from lyngdorf.const import LyngdorfModel
from lyngdorf.device import async_find_receiver_model
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from .const import (
    CONF_MANUFACTURER,
    CONF_SERIAL_NUMBER,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    SUPPORTED_MANUFACTURERS,
)

FlowInput = Mapping[str, Any] | None


class LyngdorfFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Lyngdorf config flow the mac address is used for the device ID."""

    def __init__(self) -> None:
        """Initialize flow."""
        self._discoveries: dict[str, SsdpServiceInfo] = {}
        self._location: str | None = None
        self._device_manufacturer: str | None = None
        self._device_model: str | None = None
        self._device_serial_number: str | None = None
        self._name: str | None = None
        self._host: str

    async def async_step_user(self, user_input: FlowInput = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user.

        Let user choose from a list of found and unconfigured devices or to
        enter an URL manually.
        """

        if user_input is not None:
            if not (name := user_input.get(CONF_NAME)):
                # No device chosen, user might want to directly enter an URL
                return await self.async_step_manual()
            # User has chosen a device, ask for confirmation
            discovery = self._discoveries[name]
            await self._async_set_info_from_discovery(discovery)
            return await self._create_entry()

        if not (discoveries := await self._async_get_discoveries()):
            # Nothing found, maybe the user knows an URL to try
            return await self.async_step_manual()

        self._discoveries = {
            discovery.upnp.get(ATTR_UPNP_FRIENDLY_NAME)
            or cast(str, urlparse(discovery.ssdp_location).hostname): discovery
            for discovery in discoveries
        }

        data_schema = vol.Schema(
            {vol.Optional(CONF_NAME): vol.In(self._discoveries.keys())}
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_manual(self, user_input: FlowInput = None) -> ConfigFlowResult:
        """Manual hostname entry by the user."""
        errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input[CONF_NAME]
            self._device_serial_number = user_input[CONF_SERIAL_NUMBER].lower()
            model: LyngdorfModel | None = None

            try:
                model = await async_find_receiver_model(self._host)
                if not model:
                    errors["base"] = "unsupported_model"
            except TimeoutError:
                errors["base"] = "timeout_connect"
            except (ConnectionError, OSError):
                errors["base"] = "cannot_connect"
            except AbortFlow:
                raise
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

            if not errors and model:
                self._device_manufacturer = model.manufacturer
                self._device_model = model.model
                await self.async_set_unique_id(self._device_serial_number)
                self._abort_if_unique_id_configured()
                return await self._create_entry()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_DEVICE_NAME): cv.string,
                vol.Required(CONF_SERIAL_NUMBER): cv.string,
            }
        )

        return self.async_show_form(
            step_id="manual", data_schema=data_schema, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by SSDP discovery."""

        await self._async_set_info_from_discovery(discovery_info)

        self.context["title_placeholders"] = {"name": self._name or "Lyngdorf"}

        return await self.async_step_confirm()

    async def async_step_ignore(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Ignore this config flow."""
        unique_id = user_input["unique_id"]
        await self.async_set_unique_id(unique_id, raise_on_progress=False)

        return self.async_create_entry(
            title=user_input["title"],
            data={
                CONF_MODEL: self._device_model,
                CONF_MANUFACTURER: self._device_manufacturer,
                CONF_SERIAL_NUMBER: self._device_serial_number,
                CONF_HOST: urlparse(self._location).hostname,
            },
        )

    async def async_step_unignore(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Rediscover previously ignored devices by their unique_id."""
        unique_id = user_input["unique_id"]
        await self.async_set_unique_id(unique_id)

        self.context["title_placeholders"] = {"name": self._name or "Lyngdorf"}

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: FlowInput = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return await self._create_entry()

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

    async def _create_entry(self) -> ConfigFlowResult:
        """Create a config entry, assuming all required information is now known."""
        title: str
        if self._location:
            title = "" + (
                self._name or urlparse(self._location).hostname or DEFAULT_DEVICE_NAME
            )
        else:
            title = self._name or DEFAULT_DEVICE_NAME

        data = {
            CONF_MODEL: self._device_model,
            CONF_MANUFACTURER: self._device_manufacturer,
            CONF_SERIAL_NUMBER: self._device_serial_number,
            CONF_HOST: self._host,
        }
        # unique_id is already set by calling function (async_step_manual, etc.)
        # Don't overwrite it here
        return self.async_create_entry(title=title, data=data)

    async def _async_set_info_from_discovery(
        self, discovery_info: SsdpServiceInfo, abort_if_configured: bool = True
    ) -> None:
        """Set information required for a config entry from the SSDP discovery."""

        if not self._location:
            self._location = discovery_info.ssdp_location
            assert isinstance(self._location, str)

        self._host = str(
            discovery_info.ssdp_headers.get("_host")
            or urlparse(self._location).hostname
        )

        self._device_model = discovery_info.upnp.get(ATTR_UPNP_MODEL_NAME) or ""
        self._device_serial_number = (
            discovery_info.upnp.get(ATTR_UPNP_SERIAL) or ""
        ).lower()
        self._device_manufacturer = (
            discovery_info.upnp.get(ATTR_UPNP_MANUFACTURER) or ""
        )

        # self._device_type = discovery_info.ssdp_nt or discovery_info.ssdp_st
        self._name = (
            discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME)
            or urlparse(self._location).hostname
            or DEFAULT_DEVICE_NAME
        )

        # Prefer the device serial number as the unique_id.
        unique_id = self._device_serial_number or f"{self._device_model}:{self._host}"
        await self.async_set_unique_id(unique_id, raise_on_progress=abort_if_configured)

        if abort_if_configured:
            self._abort_if_unique_id_configured(reload_on_update=False)

    async def _async_get_discoveries(self) -> list[SsdpServiceInfo]:
        """Get list of unconfigured DLNA devices discovered by SSDP."""

        # Get all compatible devices from ssdp's cache
        discoveries: list[SsdpServiceInfo] = []
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
            disc for disc in discoveries if disc.ssdp_udn not in current_unique_ids
        ]

        return [disc for disc in discoveries if _is_lyngdorf_device(disc)]


def _is_lyngdorf_device(discovery_info: SsdpServiceInfo) -> bool:
    # Special cases for devices with other discovery methods (e.g. mDNS), or
    # that advertise multiple unrelated (sent in separate discovery packets)
    # UPnP devices.
    manufacturer = (discovery_info.upnp.get(ATTR_UPNP_MANUFACTURER) or "").lower()

    if manufacturer in map(str.lower, SUPPORTED_MANUFACTURERS):
        # one of ours
        return True

    return False
