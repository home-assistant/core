"""Config flow for the Zentraly integration."""

import logging
from typing import Any, override

import probatio
from zentraly import ZentralyApi, ZentralyAuthenticationError, ZentralyConnectionError

from homeassistant.config_entries import ConfigFlow as HAConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN
from .platforms import get_device_platforms

_LOGGER = logging.getLogger(__name__)
PASSWORD_SCHEMA = probatio.Schema({probatio.Required(CONF_PASSWORD): str})


class ZentralyConfigFlow(HAConfigFlow, domain=DOMAIN):
    """Handle discovery and authentication of Zentraly thermostats."""

    def __init__(self) -> None:
        """Initialize discovery data."""
        self.data: dict[str, Any] = {}

    @override
    async def async_step_zeroconf(
        self,
        discovery_info: ZeroconfServiceInfo,
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""

        device_id = discovery_info.name.split(".")[0]

        if not get_device_platforms(device_id):
            return self.async_abort(reason="unsupported_device")

        self.data[CONF_HOST] = discovery_info.host
        self.data[CONF_PORT] = discovery_info.port
        self.data[CONF_DEVICE_ID] = device_id

        self.context.update(
            {
                "title_placeholders": {
                    "name": device_id,
                }
            }
        )

        _LOGGER.info(
            "Zentraly device discovered: %s at %s:%s",
            device_id,
            self.data[CONF_HOST],
            self.data[CONF_PORT],
        )

        await self.async_set_unique_id(device_id)

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: discovery_info.host,
                CONF_PORT: discovery_info.port,
            },
            reload_on_update=False,
        )

        return await self.async_step_auth()

    async def async_step_auth(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle password authentication."""

        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]

            api = ZentralyApi(
                session=async_get_clientsession(self.hass),
                host=self.data[CONF_HOST],
                port=self.data[CONF_PORT],
                password=password,
                device_id=self.data[CONF_DEVICE_ID],
            )

            try:
                mac = await api.async_validate_password()

            except ZentralyAuthenticationError:
                errors["base"] = "invalid_auth"

            except ZentralyConnectionError:
                errors["base"] = "cannot_connect"

            else:
                self.data[CONF_PASSWORD] = password
                self.data[CONF_MAC] = mac

                _LOGGER.info(
                    "Zentraly device validated: device_id=%s mac=%s ip=%s",
                    self.data[CONF_DEVICE_ID],
                    mac,
                    self.data[CONF_HOST],
                )

                return self.async_create_entry(
                    title=self.data[CONF_DEVICE_ID],
                    data=self.data,
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=PASSWORD_SCHEMA,
            errors=errors,
            description_placeholders=self.context["title_placeholders"],
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain that supported thermostats must be discovered locally."""
        return self.async_abort(reason="zeroconf_only")
