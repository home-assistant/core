"""Config flow for E3/DC devices."""

from collections.abc import Iterable, Mapping
from ipaddress import IPv4Address, IPv6Address, ip_interface
import logging
from typing import Any, override

from e3dc_ess_modbus import E3dcPowerStation, NotAnE3dcError
from modbus_connection import ModbusError, ModbusTcpParams
import probatio

from homeassistant.components import network
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN, UNIT_ID

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
    }
)


def create_modbus_params(data: Mapping[str, Any]) -> ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


async def _async_probe(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> E3dcPowerStation:
    """Connect to the power station and read its identity, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, UNIT_ID) as unit:
        device = E3dcPowerStation(unit)
        try:
            await device.async_ensure_setup()
        finally:
            # The station listens to the shared connection until it is closed
            device.close()
        return device


async def _async_local_ipv4(
    hass: HomeAssistant, addresses: Iterable[IPv4Address | IPv6Address]
) -> str | None:
    """Return the first IPv4 address on a subnet Home Assistant is connected to."""
    # The power station announces multiple IP addresses on multiple networks.
    # Find one that HA can connect to.
    subnets = [
        ip_interface(f"{ipv4['address']}/{ipv4['network_prefix']}").network
        for adapter in await network.async_get_adapters(hass)
        for ipv4 in adapter["ipv4"]
    ]
    for address in addresses:
        if isinstance(address, IPv4Address) and any(
            address in subnet for subnet in subnets
        ):
            return str(address)
    return None


def _title(model: str | None) -> str:
    """Name the power station after the brand and its model, e.g. E3/DC One."""
    if not model:
        return DEFAULT_NAME
    # The E3/DC one reports its model in lower case
    return f"{DEFAULT_NAME} {model[0].upper()}{model[1:]}"


class E3dcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an E3/DC config flow."""

    VERSION = 1

    _discovered_host: str
    _discovered_name: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask where the power station is, then probe it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device, errors = await self._async_validate(user_input)
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_title(device.model), data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a power station announcing its EEBus service."""
        host = await _async_local_ipv4(self.hass, discovery_info.ip_addresses)
        if host is None:
            return self.async_abort(reason="no_local_address")

        # The EEBus ID is the serial number the power station reports over Modbus
        serial_number = discovery_info.properties["id"]
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        device, errors = await self._async_validate(
            {CONF_HOST: host, CONF_PORT: DEFAULT_PORT}
        )
        if device is None:
            return self.async_abort(reason=errors["base"])

        self._discovered_host = host
        # The announced model is generic, so name the card after the probed one
        self._discovered_name = _title(device.model)
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setting up the discovered power station."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name,
                data={CONF_HOST: self._discovered_host, CONF_PORT: DEFAULT_PORT},
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._discovered_name,
                "host": self._discovered_host,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle updating an existing entry's connection details."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            device, errors = await self._async_validate(user_input)
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[E3dcPowerStation | None, dict[str, str]]:
        """Probe the power station, returning it or the errors to show instead."""
        try:
            device = await _async_probe(self.hass, data)
        except NotAnE3dcError:
            return None, {"base": "not_e3dc"}
        except (ModbusError, HomeAssistantError) as err:
            _LOGGER.debug("Could not reach the power station: %r", err)
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error while probing the power station")
            return None, {"base": "unknown"}

        if not device.serial_number:
            return None, {"base": "no_serial_number"}

        return device, {}
