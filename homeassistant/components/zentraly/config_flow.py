"""Config flow for the Zentraly integration."""

from ipaddress import IPv4Address
import logging
from typing import Any, override

import probatio
from zentraly import ZentralyApi, ZentralyAuthenticationError, ZentralyConnectionError

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow as HAConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import get_device_platforms
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DEFAULT_PORT = 80
PASSWORD_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        )
    }
)
MANUAL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_DEVICE_ID): TextSelector(),
        **PASSWORD_SCHEMA.schema,
    }
)


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

        _LOGGER.debug(
            "Zentraly device discovered: %s at %s:%s",
            device_id,
            self.data[CONF_HOST],
            self.data[CONF_PORT],
        )

        await self.async_set_unique_id(device_id)

        if (
            (
                entry := self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, device_id
                )
            )
            and entry.state is ConfigEntryState.SETUP_ERROR
            and entry.error_reason_translation_key == "unexpected_device"
            and (entry.data[CONF_HOST], entry.data[CONF_PORT])
            != (discovery_info.host, discovery_info.port)
        ):
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_HOST: discovery_info.host,
                    CONF_PORT: discovery_info.port,
                },
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: discovery_info.host,
                CONF_PORT: discovery_info.port,
            },
        )

        return await self.async_step_auth()

    async def async_step_auth(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle password authentication."""

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title=self.data[CONF_DEVICE_ID], data=self.data
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=PASSWORD_SCHEMA,
            errors=errors,
            description_placeholders=self.context["title_placeholders"],
        )

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate credentials through the public library API."""
        errors: dict[str, str] = {}

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
            self._async_abort_entries_match({CONF_MAC: mac})
            self.data[CONF_PASSWORD] = password
            self.data[CONF_MAC] = mac

            _LOGGER.debug(
                "Zentraly device validated: device_id=%s mac=%s ip=%s",
                self.data[CONF_DEVICE_ID],
                mac,
                self.data[CONF_HOST],
            )

        return errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to add a Zentraly device."""
        return self.async_show_menu(step_id="user", menu_options=["manual"])

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a supported thermostat using its connection details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            host = user_input[CONF_HOST].strip()
            try:
                IPv4Address(host)
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            if not get_device_platforms(device_id):
                errors[CONF_DEVICE_ID] = "unsupported_device"
            if not errors:
                await self.async_set_unique_id(device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                self.data = {
                    CONF_HOST: host,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_DEVICE_ID: device_id,
                }
                errors = await self._async_validate_input(user_input)
                if not errors:
                    return self.async_create_entry(title=device_id, data=self.data)

        return self.async_show_form(
            step_id="manual", data_schema=MANUAL_SCHEMA, errors=errors
        )
