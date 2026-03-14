"""Config flow for Lyngdorf integration."""

from __future__ import annotations

from functools import partial
from typing import Any
from urllib.parse import urlparse

from async_upnp_client.profiles.dlna import DmrDevice
import getmac
from lyngdorf.const import LyngdorfModel
from lyngdorf.device import async_find_receiver_model
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
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
    CONF_SERIAL_NUMBER,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    SUPPORTED_MANUFACTURERS,
)


class LyngdorfFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Lyngdorf config flow."""

    def __init__(self) -> None:
        """Initialize flow."""
        self._location: str | None = None
        self._device_model: str | None = None
        self._device_serial_number: str | None = None
        self._name: str | None = None
        self._host: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_manual(user_input)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual hostname entry by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            model: LyngdorfModel | None = None

            try:
                model = await async_find_receiver_model(self._host)
            except TimeoutError:
                errors["base"] = "timeout_connect"
            except OSError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

            if not errors and not model:
                errors["base"] = "unsupported_model"

            if not errors and model:
                self._device_model = model.model_name
                self._name = model.model_name

                # Resolve MAC address from ARP table to use as serial
                if mac := await self.hass.async_add_executor_job(
                    partial(getmac.get_mac_address, ip=self._host)
                ):
                    self._device_serial_number = mac.replace(":", "").lower()

                # Check SSDP discoveries for matching host to get name
                discovery = await self._async_find_discovery_by_host(self._host)
                if discovery:
                    if not self._device_serial_number:
                        self._device_serial_number = (
                            discovery.upnp.get(ATTR_UPNP_SERIAL) or ""
                        ).lower() or None
                    self._name = (
                        discovery.upnp.get(ATTR_UPNP_FRIENDLY_NAME) or self._name
                    )

                unique_id = (
                    self._device_serial_number or f"{self._device_model}:{self._host}"
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return await self._create_entry()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by SSDP discovery."""

        await self._async_set_info_from_discovery(discovery_info)

        display_name = (
            f"{self._device_model} ({self._name})"
            if self._device_model and self._device_model != self._name
            else self._name or DEFAULT_DEVICE_NAME
        )
        self.context["title_placeholders"] = {"name": display_name}

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return await self._create_entry()

        display_name = (
            f"{self._device_model} ({self._name})"
            if self._device_model and self._device_model != self._name
            else self._name or DEFAULT_DEVICE_NAME
        )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": display_name},
        )

    async def _create_entry(self) -> ConfigFlowResult:
        """Create a config entry, assuming all required information is now known."""
        if self._location:
            title = (
                self._name or urlparse(self._location).hostname or DEFAULT_DEVICE_NAME
            )
        else:
            title = self._name or DEFAULT_DEVICE_NAME

        data: dict[str, Any] = {
            CONF_MODEL: self._device_model,
            CONF_HOST: self._host,
        }
        if self._device_serial_number:
            data[CONF_SERIAL_NUMBER] = self._device_serial_number

        return self.async_create_entry(title=title, data=data)

    async def _async_set_info_from_discovery(
        self, discovery_info: SsdpServiceInfo, abort_if_configured: bool = True
    ) -> None:
        """Set information required for a config entry from the SSDP discovery."""

        if not self._location:
            self._location = discovery_info.ssdp_location
            assert isinstance(self._location, str)

        if hostname := (
            discovery_info.ssdp_headers.get("_host")
            or urlparse(self._location).hostname
        ):
            self._host = str(hostname)
        else:
            raise AbortFlow("cannot_connect")

        self._device_model = discovery_info.upnp.get(ATTR_UPNP_MODEL_NAME) or ""
        self._device_serial_number = (
            discovery_info.upnp.get(ATTR_UPNP_SERIAL) or ""
        ).lower() or None
        self._name = (
            discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME)
            or urlparse(self._location).hostname
            or DEFAULT_DEVICE_NAME
        )

        # Prefer the device serial number as the unique_id
        unique_id = self._device_serial_number or f"{self._device_model}:{self._host}"
        await self.async_set_unique_id(unique_id, raise_on_progress=abort_if_configured)

        if abort_if_configured:
            self._abort_if_unique_id_configured(reload_on_update=False)

    async def _async_find_discovery_by_host(self, host: str) -> SsdpServiceInfo | None:
        """Find an SSDP discovery matching the given host."""
        for udn_st in DmrDevice.DEVICE_TYPES:
            discoveries = await ssdp.async_get_discovery_info_by_st(self.hass, udn_st)
            for disc in discoveries:
                if not _is_lyngdorf_device(disc):
                    continue
                disc_host = (
                    disc.ssdp_headers.get("_host")
                    or urlparse(disc.ssdp_location or "").hostname
                )
                if disc_host == host:
                    return disc
        return None


def _is_lyngdorf_device(discovery_info: SsdpServiceInfo) -> bool:
    """Check if the discovered device is a Lyngdorf device."""
    manufacturer = (discovery_info.upnp.get(ATTR_UPNP_MANUFACTURER) or "").lower()
    return manufacturer in map(str.lower, SUPPORTED_MANUFACTURERS)
