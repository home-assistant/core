"""Config flow for Lyngdorf integration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from lyngdorf.device import (
    async_find_receiver_model,
    async_get_device_serial,
    lookup_receiver_model,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from .const import CONF_SERIAL_NUMBER, DEFAULT_DEVICE_NAME, DOMAIN


class LyngdorfFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Lyngdorf config flow."""

    def __init__(self) -> None:
        """Initialize flow."""
        self._location: str | None = None
        self._device_model: str | None = None
        self._device_serial_number: str | None = None
        self._name: str | None = None
        self._host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]

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

                serial = await async_get_device_serial(self._host)
                if not serial:
                    errors["base"] = "cannot_determine_id"
                else:
                    self._device_serial_number = serial
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured()
                    return await self._create_entry()

        return self.async_show_form(
            step_id="user",
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
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await async_find_receiver_model(self._host)
            except TimeoutError, OSError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

            if not errors:
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
            errors=errors,
        )

    async def _create_entry(self) -> ConfigFlowResult:
        """Create a config entry."""
        assert self._host
        assert self._device_model
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
        self, discovery_info: SsdpServiceInfo
    ) -> None:
        """Set information required for a config entry from SSDP discovery."""
        if not self._location:
            self._location = discovery_info.ssdp_location
            if not isinstance(self._location, str):
                raise AbortFlow("cannot_connect")

        if hostname := (
            discovery_info.ssdp_headers.get("_host")
            or urlparse(self._location).hostname
        ):
            self._host = str(hostname)
        else:
            raise AbortFlow("cannot_connect")

        device_model_name = discovery_info.upnp.get(ATTR_UPNP_MODEL_NAME) or ""
        if not (model := lookup_receiver_model(device_model_name)):
            raise AbortFlow("unsupported_model")
        self._device_model = model.model_name
        self._device_serial_number = (
            discovery_info.upnp.get(ATTR_UPNP_SERIAL) or ""
        ).lower() or None
        self._name = (
            discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME)
            or urlparse(self._location).hostname
            or DEFAULT_DEVICE_NAME
        )

        if not self._device_serial_number:
            raise AbortFlow("cannot_connect")
        await self.async_set_unique_id(self._device_serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
