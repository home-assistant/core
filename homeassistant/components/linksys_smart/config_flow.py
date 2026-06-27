"""Config flow for the linksys integration."""

from collections.abc import Mapping
import logging
from typing import Any, Self, override
from urllib.parse import urlparse

from jnap import JNAPClient, JNAPError, JNAPUnauthorizedError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_SSDP_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    kwargs: dict[str, Any] = {}
    if username := data.get(CONF_USERNAME):
        kwargs["username"] = username
    client = JNAPClient(
        data[CONF_HOST], async_get_clientsession(hass), data[CONF_PASSWORD], **kwargs
    )
    try:
        device_info = await client.get_device_info()
    except JNAPError as err:
        raise CannotConnect from err
    try:
        await client.get_devices()
    except JNAPUnauthorizedError as err:
        raise InvalidAuth from err
    except JNAPError as err:
        raise CannotConnect from err
    return {
        "title": device_info.description,
        "serial_number": device_info.serial_number,
    }


async def _async_validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Validate user input and map exceptions to form errors."""
    errors: dict[str, str] = {}
    try:
        info = await validate_input(hass, data)
    except CannotConnect:
        errors["base"] = "cannot_connect"
        info = None
    except InvalidAuth:
        errors["base"] = "invalid_auth"
        info = None
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
        info = None
    return info, errors


class LinksysConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for linksys."""

    VERSION = 1
    _MANUFACTURER = "Linksys"
    _UDN_PREFIX = "uuid:"

    _host: str

    @override
    def is_matching(self, other_flow: Self) -> bool:
        return self._host == other_flow._host

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        if discovery_info.upnp.get(ATTR_UPNP_MANUFACTURER) != self._MANUFACTURER:
            return self.async_abort(reason="not_linksys_device")

        host = urlparse(discovery_info.ssdp_location or "").hostname
        if not host:
            return self.async_abort(reason="cannot_connect")

        self._host = host

        if udn := discovery_info.upnp.get(ATTR_UPNP_UDN):
            await self.async_set_unique_id(udn.removeprefix(self._UDN_PREFIX))
            self._abort_if_unique_id_configured({CONF_HOST: host})

        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")

        self.context.update(
            {
                "title_placeholders": {
                    "name": discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME, host)
                },
                "configuration_url": f"http://{host}",
            }
        )
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered device and collect credentials."""
        if user_input is not None:
            data = {CONF_HOST: self._host, **user_input}
            info, errors = await _async_validate_input(self.hass, data)
            if info is not None:
                return self.async_create_entry(title=info["title"], data=data)
        else:
            errors = {}

        return self.async_show_form(
            step_id="confirm",
            data_schema=STEP_SSDP_DATA_SCHEMA,
            description_placeholders={"host": self._host},
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            info, errors = await _async_validate_input(self.hass, user_input)
            if info is not None:
                await self.async_set_unique_id(info["serial_number"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
        else:
            errors = {}

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when credentials are rejected by the router."""
        self.context["title_placeholders"] = {"host": entry_data[CONF_HOST]}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm updated credentials."""
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            _, errors = await _async_validate_input(
                self.hass, {**reauth_entry.data, **user_input}
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )
        else:
            errors = {}

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_SSDP_DATA_SCHEMA,
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
