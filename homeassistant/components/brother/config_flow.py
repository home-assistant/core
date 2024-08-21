"""Adds config flow for Brother Printer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from brother import Brother, SnmpError, UnsupportedModelError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.components.snmp import async_get_snmp_engine
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.network import is_host_valid

from .const import DOMAIN, PRINTER_TYPES

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_TYPE, default="laser"): vol.In(PRINTER_TYPES),
    }
)
RECONFIGURE_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any], expected_mac: str | None = None
) -> tuple[str, str]:
    """Validate the user input."""
    if not is_host_valid(user_input[CONF_HOST]):
        raise InvalidHost

    snmp_engine = await async_get_snmp_engine(hass)

    brother = await Brother.create(user_input[CONF_HOST], snmp_engine=snmp_engine)
    await brother.async_update()

    if expected_mac is not None and brother.serial.lower() != expected_mac:
        raise AnotherDevice

    return (brother.model, brother.serial)


class BrotherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brother Printer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.brother: Brother
        self.host: str | None = None
        self.entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                model, serial = await validate_input(self.hass, user_input)
            except InvalidHost:
                errors[CONF_HOST] = "wrong_host"
            except (ConnectionError, TimeoutError):
                errors["base"] = "cannot_connect"
            except SnmpError:
                errors["base"] = "snmp_error"
            except UnsupportedModelError:
                return self.async_abort(reason="unsupported_model")
            else:
                await self.async_set_unique_id(serial.lower())
                self._abort_if_unique_id_configured()

                title = f"{model} {serial}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info.host

        # Do not probe the device if the host is already configured
        self._async_abort_entries_match({CONF_HOST: self.host})

        snmp_engine = await async_get_snmp_engine(self.hass)
        model = discovery_info.properties.get("product")

        try:
            self.brother = await Brother.create(
                self.host, snmp_engine=snmp_engine, model=model
            )
            await self.brother.async_update()
        except UnsupportedModelError:
            return self.async_abort(reason="unsupported_model")
        except (ConnectionError, SnmpError, TimeoutError):
            return self.async_abort(reason="cannot_connect")

        # Check if already configured
        await self.async_set_unique_id(self.brother.serial.lower())
        self._abort_if_unique_id_configured({CONF_HOST: self.host})

        self.context.update(
            {
                "title_placeholders": {
                    "serial_number": self.brother.serial,
                    "model": self.brother.model,
                }
            }
        )
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is not None:
            title = f"{self.brother.model} {self.brother.serial}"
            return self.async_create_entry(
                title=title,
                data={CONF_HOST: self.host, CONF_TYPE: user_input[CONF_TYPE]},
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_TYPE, default="laser"): vol.In(PRINTER_TYPES)}
            ),
            description_placeholders={
                "serial_number": self.brother.serial,
                "model": self.brother.model,
            },
        )

    async def async_step_reconfigure(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if TYPE_CHECKING:
            assert entry is not None

        self.entry = entry

        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors = {}

        if TYPE_CHECKING:
            assert self.entry is not None

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input, self.entry.unique_id)
            except InvalidHost:
                errors[CONF_HOST] = "wrong_host"
            except (ConnectionError, TimeoutError):
                errors["base"] = "cannot_connect"
            except SnmpError:
                errors["base"] = "snmp_error"
            except AnotherDevice:
                errors["base"] = "another_device"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data=self.entry.data | {CONF_HOST: user_input[CONF_HOST]},
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=RECONFIGURE_SCHEMA,
                suggested_values=self.entry.data | (user_input or {}),
            ),
            description_placeholders={"printer_name": self.entry.title},
            errors=errors,
        )


class InvalidHost(HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""


class AnotherDevice(HomeAssistantError):
    """Error to indicate that hostname/IP address belongs to another device."""
