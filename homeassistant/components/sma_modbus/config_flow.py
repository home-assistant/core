"""Config flow for the SMA Modbus integration."""

import logging
import re
from typing import Any

from modbus_connection import ModbusError, ModbusTcpParams
from sma_modbus import DEVICE_CLASSES, DeviceType, DiscoveryInfo, discover
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .connection import ModbusUnitConnection
from .const import (
    CONF_DEVICE_TYPE,
    CONF_UNIT_ID,
    CONF_WEB_PORT,
    DEFAULT_PORT,
    DEVICE_NAMES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_PORT = NumberSelector(
    NumberSelectorConfig(min=502, max=65535, step=1, mode=NumberSelectorMode.BOX)
)

_UNIT_ID = vol.All(
    NumberSelector(
        NumberSelectorConfig(min=0, max=123, step=1, mode=NumberSelectorMode.BOX)
    ),
    vol.Coerce(int),
)


def _schema(suggested_values: dict[str, Any] | None = None) -> vol.Schema:
    """Build the user form schema."""
    suggested = suggested_values or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=suggested.get(CONF_HOST),
            ): TextSelector(),
            vol.Required(
                CONF_PORT,
                default=suggested.get(CONF_PORT, DEFAULT_PORT),
            ): _PORT,
            vol.Optional(
                CONF_UNIT_ID,
                default=suggested.get(CONF_UNIT_ID, 0),
            ): _UNIT_ID,
        }
    )


def _extract_serial(hostname: str) -> str | None:
    """Extract the serial number from an SMA mDNS hostname.

    SMA devices advertise hostnames like ``SMA12345678.local``.
    Returns the numeric serial as a string, or ``None``.
    """
    match = re.match(r"SMA(\d+)", hostname, re.IGNORECASE)
    return match.group(1) if match else None


async def _async_discover(
    hass: HomeAssistant,
    host: str,
    port: int,
    unit_id: int | None = None,
) -> DiscoveryInfo | None:
    """Discover the SMA device at ``host:port``.

    Uses the shared modbus connection to probe the device.
    """
    try:
        async with async_get_temporary_unit(
            hass, ModbusTcpParams(host=host, port=port), unit_id
        ) as unit:
            adapter = ModbusUnitConnection(unit)
            return await discover(adapter, unit_id=unit_id)
    except ModbusError, OSError:
        return None


class SmaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_data: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery.

        Extracts the serial from the mDNS hostname (``SMA<serial>.local``),
        sets the unique ID, and discovers the device type and unit ID.
        If already configured, updates the host if it changed.
        """
        host = discovery_info.host
        serial = _extract_serial(discovery_info.hostname)
        if serial is None:
            # No serial in hostname — fall through to manual setup.
            self._discovered_data = {CONF_HOST: host}
            return await self.async_step_user()

        unique_id = f"SMA{serial}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Discover the device type and unit ID.
        info = await _async_discover(self.hass, host, DEFAULT_PORT, unit_id=None)
        if info is None or str(info.serial_number) != serial:
            # Can't discover or serial mismatch — fall through to manual setup.
            self._discovered_data = {CONF_HOST: host}
            return await self.async_step_user()

        self._discovered_data = {
            CONF_DEVICE_TYPE: info.device_type.value,
            CONF_HOST: host,
            CONF_PORT: DEFAULT_PORT,
        }
        if discovery_info.port:
            self._discovered_data[CONF_WEB_PORT] = discovery_info.port
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_data[CONF_HOST],
                data=self._discovered_data,
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "device": DEVICE_NAMES[
                    DeviceType(self._discovered_data[CONF_DEVICE_TYPE])
                ],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])
            unit_id = user_input.get(CONF_UNIT_ID) or 0
            if unit_id == 0:
                unit_id = None
            info = await _async_discover(self.hass, host, port, unit_id=unit_id)
            if info is None:
                errors["base"] = "cannot_connect"
            else:
                unique_id = f"SMA{info.serial_number}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                data: dict[str, Any] = {
                    CONF_DEVICE_TYPE: info.device_type.value,
                    CONF_HOST: host,
                    CONF_PORT: port,
                }
                if info.unit_id != DEVICE_CLASSES[info.device_type].default_unit_id:
                    data[CONF_UNIT_ID] = info.unit_id
                return self.async_create_entry(
                    title=host,
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self._discovered_data or None),
            errors=errors,
        )
