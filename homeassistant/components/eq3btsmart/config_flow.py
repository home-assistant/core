"""Config flow for eQ-3 Bluetooth Smart thermostats."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_RSSI, DOMAIN
from .schemas import SCHEMA_NAME, SCHEMA_NAME_MAC

_LOGGER = logging.getLogger(__name__)


class EQ3ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for eQ-3 Bluetooth Smart thermostats."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""

        self.discovery_info = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] | None = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_NAME_MAC,
                errors=errors,
            )

        await self.async_set_unique_id(format_mac(user_input[CONF_MAC]))
        self._abort_if_unique_id_configured(updates=user_input)
        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""

        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self.discovery_info = discovery_info
        name = self.discovery_info.device.name or self.discovery_info.name
        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: name,
                    CONF_MAC: discovery_info.address,
                    CONF_RSSI: discovery_info.rssi,
                }
            }
        )
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow start."""

        if self.discovery_info is None:
            return self.async_abort(reason="not_supported")

        self._async_abort_entries_match({CONF_MAC: self.discovery_info.address})

        if user_input is None:
            name = self.discovery_info.device.name or self.discovery_info.name
            return self.async_show_form(
                step_id="init",
                data_schema=SCHEMA_NAME(default_name=name),
                description_placeholders={
                    CONF_NAME: name,
                    CONF_MAC: self.discovery_info.address,
                    CONF_RSSI: str(self.discovery_info.rssi),
                },
            )
        await self.async_set_unique_id(format_mac(self.discovery_info.address))
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_NAME: user_input[CONF_NAME],
                CONF_MAC: self.discovery_info.address,
            },
        )
