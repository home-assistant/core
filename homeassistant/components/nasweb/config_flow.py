"""Config flow for NASweb integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from webio_api import WebioAPI
from webio_api.api_client import AuthError

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError

from .const import DOMAIN
from .coordinator import NASwebCoordinator
from .nasweb_data import NASwebData

NASWEB_SCHEMA_IMG_URL = (
    "https://home-assistant.io/images/integrations/nasweb/nasweb_scheme.png"
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user-provided data."""
    webio_api = WebioAPI(data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
    if not await webio_api.check_connection():
        raise CannotConnect
    try:
        await webio_api.refresh_device_info()
    except AuthError as e:
        raise InvalidAuth from e

    nasweb_data = NASwebData()
    nasweb_data.initialize(hass)
    try:
        webio_serial = webio_api.get_serial_number()
        if webio_serial is None:
            raise MissingNASwebData("Device serial number is not available")

        coordinator = NASwebCoordinator(hass, webio_api)
        webhook_url = nasweb_data.get_webhook_url(hass)
        nasweb_data.notify_coordinator.add_coordinator(webio_serial, coordinator)
        subscription = await webio_api.status_subscription(webhook_url, True)
        if not subscription:
            nasweb_data.notify_coordinator.remove_coordinator(webio_serial)
            raise MissingNASwebData(
                "Failed to subscribe for status updates from device"
            )

        result = await nasweb_data.notify_coordinator.check_connection(webio_serial)
        nasweb_data.notify_coordinator.remove_coordinator(webio_serial)
        if not result:
            if subscription:
                await webio_api.status_subscription(webhook_url, False)
            raise MissingNASwebStatus("Did not receive status from device")

        name = webio_api.get_name()
    finally:
        nasweb_data.deinitialize(hass)
    return {"title": name, CONF_UNIQUE_ID: webio_serial}


class NASwebConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NASweb."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(info[CONF_UNIQUE_ID])
                self._abort_if_unique_id_configured()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoURLAvailableError:
                errors["base"] = "missing_internal_url"
            except MissingNASwebData:
                errors["base"] = "missing_nasweb_data"
            except MissingNASwebStatus:
                errors["base"] = "missing_status"
            except AbortFlow:
                raise
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "nasweb_schema_img": '<img src="' + NASWEB_SCHEMA_IMG_URL + '"/><br>',
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class MissingNASwebData(HomeAssistantError):
    """Error to indicate missing information from NASweb."""


class MissingNASwebStatus(HomeAssistantError):
    """Error to indicate there was no status received from NASweb."""
