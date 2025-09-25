"""Config flow for eQ-3 Bluetooth Smart thermostats."""

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util import slugify

from .const import CONF_MAC_ADDRESS, DOMAIN

SCHEMA_MAC = vol.Schema(
    {
        vol.Required(CONF_MAC_ADDRESS): str,
    }
)


class EQ3ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for eQ-3 Bluetooth Smart thermostats."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.mac_address: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_MAC,
                errors=errors,
            )

        mac_address = format_mac(user_input[CONF_MAC_ADDRESS])

        if not validate_mac(mac_address):
            errors[CONF_MAC_ADDRESS] = "invalid_mac_address"
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_MAC,
                errors=errors,
            )

        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates=user_input)

        # We can not validate if this mac actually is an eQ-3 thermostat,
        # since the thermostat might not be advertising right now.
        return self.async_create_entry(
            title=slugify(mac_address), data={CONF_MAC_ADDRESS: mac_address}
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery."""
        self.mac_address = format_mac(discovery_info.address)

        await self.async_set_unique_id(self.mac_address)
        self._abort_if_unique_id_configured()

        self.context.update(
            {"title_placeholders": {CONF_MAC_ADDRESS: self.mac_address}}
        )

        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle flow start."""
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                description_placeholders={CONF_MAC_ADDRESS: self.mac_address},
            )

        await self.async_set_unique_id(self.mac_address)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=slugify(self.mac_address),
            data={CONF_MAC_ADDRESS: self.mac_address},
        )


def validate_mac(mac: str) -> bool:
    """Return whether or not given value is a valid MAC address."""
    return bool(
        mac
        and len(mac) == 17
        and mac.count(":") == 5
        and all(int(part, 16) < 256 for part in mac.split(":") if part)
    )
