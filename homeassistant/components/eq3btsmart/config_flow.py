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

    def __init__(self) -> None:
        """Initialize the config flow."""

        self.name = ""
        self.mac = ""
        self.rssi = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_NAME_MAC,
                errors=errors,
            )

        name = user_input[CONF_NAME]
        mac_address = user_input[CONF_MAC]

        if not validate_name(name):
            errors[CONF_NAME] = "invalid_name"
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_NAME_MAC,
                errors=errors,
            )

        if not validate_mac(mac_address):
            errors[CONF_MAC] = "invalid_mac_address"
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_NAME_MAC,
                errors=errors,
            )

        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates=user_input)
        return self.async_create_entry(title=name, data=user_input)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""

        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self.name = discovery_info.device.name or discovery_info.name
        self.mac = discovery_info.address
        self.rssi = discovery_info.rssi

        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: self.name,
                    CONF_MAC: self.mac,
                    CONF_RSSI: self.rssi,
                }
            }
        )
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow start."""

        self._async_abort_entries_match({CONF_MAC: self.mac})

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=SCHEMA_NAME(default_name=self.name),
                description_placeholders={
                    CONF_NAME: self.name,
                    CONF_MAC: self.mac,
                    CONF_RSSI: str(self.rssi),
                },
            )
        await self.async_set_unique_id(format_mac(self.mac))
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_NAME: self.name,
                CONF_MAC: self.mac,
            },
        )


def validate_mac(mac: str) -> bool:
    """Return whether or not given value is a valid MAC address."""

    return bool(
        mac
        and len(mac) == 17
        and mac.count(":") == 5
        and all(int(part, 16) < 256 for part in mac.split(":") if part)
    )


def validate_name(name: str) -> bool:
    """Return whether or not given value is a valid name."""

    return bool(name)
