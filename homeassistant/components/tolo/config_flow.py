"""Config flow for TOLO."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from tololib import ToloClient, ToloCommunicationError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import section
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import selector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    CONF_ACCESSORIES,
    CONF_ACCESSORY_AROMA_THERAPY,
    CONF_ACCESSORY_AROMA_THERAPY_TYPE,
    CONF_ACCESSORY_FAN,
    CONF_ACCESSORY_LIGHT,
    CONF_ACCESSORY_SALT_BATH,
    CONF_EXPERT,
    CONF_RETRY_COUNT,
    CONF_RETRY_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_ACCESSORIES): section(
            schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESSORY_FAN, default=True): bool,
                    vol.Required(CONF_ACCESSORY_LIGHT, default=True): bool,
                    vol.Required(CONF_ACCESSORY_SALT_BATH, default=True): bool,
                    vol.Required(CONF_ACCESSORY_AROMA_THERAPY, default=True): bool,
                    vol.Required(CONF_ACCESSORY_AROMA_THERAPY_TYPE): selector(
                        {
                            "select": {
                                "options": ["single", "dual"],
                                "translation_key": CONF_ACCESSORY_AROMA_THERAPY_TYPE,
                            }
                        }
                    ),
                }
            ),
            options={"collapsed": False},
        ),
        vol.Required(CONF_EXPERT): section(
            schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RETRY_TIMEOUT, default=DEFAULT_RETRY_TIMEOUT
                    ): int,
                    vol.Optional(CONF_RETRY_COUNT, default=DEFAULT_RETRY_COUNT): int,
                }
            ),
            options={"collapsed": True},
        ),
    }
)


class ToloConfigFlow(ConfigFlow, domain=DOMAIN):
    """ConfigFlow for the TOLO Integration."""

    _dhcp_discovery_info: DhcpServiceInfo | None = None

    @staticmethod
    def _check_device_availability(host: str) -> bool:
        client = ToloClient(host)
        try:
            result = client.get_status()
        except ToloCommunicationError:
            return False
        return result is not None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a config flow initialized by the user."""
        errors = {}

        if user_input is not None:
            device_available = await self.hass.async_add_executor_job(
                self._check_device_availability, user_input[CONF_HOST]
            )

            if device_available:
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=user_input
                    )
                return self.async_create_entry(
                    title=DEFAULT_NAME, data={CONF_HOST: user_input[CONF_HOST]}
                )

            errors["base"] = "cannot_connect"

        schema_values: dict[str, Any] | MappingProxyType[str, Any] | None = None
        if self.source == SOURCE_RECONFIGURE:
            schema_values = self._get_reconfigure_entry().data
        elif self.source == SOURCE_DHCP and self._dhcp_discovery_info is not None:
            schema_values = {CONF_HOST: self._dhcp_discovery_info.ip}
        else:
            schema_values = user_input

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA,
                schema_values,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration config flow initialized by the user."""
        return await self.async_step_user(user_input)

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured({CONF_HOST: discovery_info.ip})
        self._async_abort_entries_match({CONF_HOST: discovery_info.ip})

        device_available = await self.hass.async_add_executor_job(
            self._check_device_availability, discovery_info.ip
        )

        if device_available:
            self._dhcp_discovery_info = discovery_info
            return await self.async_step_user()
        return self.async_abort(reason="not_tolo_device")
