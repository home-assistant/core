"""Config flow for the KWB Modbus integration."""

from __future__ import annotations

import logging
import re
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    ADDON_MODULES,
    CONF_ACTIVE_INSTANCES,
    CONF_ADDON_MODULES,
    CONF_DISCOVERED_SENSORS,
    CONF_EXPERT_MODE,
    CONF_HEATING_DEVICE,
    CONF_SLAVE_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    HEATING_DEVICES,
    SENSOR_STATUS_OK,
)
from .register_map import REGISTERS, SELECT_REGISTERS

_LOGGER = logging.getLogger(__name__)

# Step 1: Host and Port (required)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Coerce(
            int
        ),
    }
)


def _natural_sort_key(s: str) -> tuple:
    """Return a sort key for natural (human-friendly) ordering of strings like 'HC 1.1'."""
    return tuple(int(p) if p.isdigit() else p for p in re.findall(r"\d+|\D+", s))


def _sorted_instances(module_key: str) -> list[str]:
    """Return naturally sorted unique instance labels available in SELECT_REGISTERS."""
    indices = {r.index for r in SELECT_REGISTERS.get(module_key, []) if r.index}
    return sorted(indices, key=_natural_sort_key)


async def _discover_active_instances(
    host: str, port: int, slave_id: int, module_key: str
) -> list[str]:
    """Connect to Modbus and discover which instances of a module have active sensors.

    For each possible instance, reads the status register (address + 1) of the
    first sensor register for that instance. Returns indices where status == OK.
    """
    # Collect one representative (index → status_address) pair per instance
    index_status: dict[str, int] = {}
    for r in REGISTERS.get(module_key, []):
        if r.index and not r.is_status and r.index not in index_status:
            index_status[r.index] = r.address + 1

    if not index_status:
        return []

    client = AsyncModbusTcpClient(host=host, port=port, timeout=5)
    active: set[str] = set()
    try:
        if not await client.connect():
            return []
        for index, status_addr in index_status.items():
            try:
                result = await client.read_input_registers(
                    address=status_addr, count=1, device_id=slave_id
                )
                if not result.isError() and result.registers[0] == SENSOR_STATUS_OK:
                    active.add(index)
            except ModbusException:
                pass
    except ModbusException:
        pass
    finally:
        if client.connected:
            client.close()

    return sorted(active, key=_natural_sort_key)


async def validate_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the Modbus connection."""
    client = AsyncModbusTcpClient(
        host=data[CONF_HOST], port=data[CONF_PORT], timeout=10
    )

    try:
        connection_result = await client.connect()
        if not connection_result:
            raise CannotConnect(  # noqa: TRY301
                f"Unable to connect to {data[CONF_HOST]}:{data[CONF_PORT]}"
            )

        result = await client.read_input_registers(address=8204, count=1)
        if result.isError():
            raise CannotConnect("Failed to read any holding registers")  # noqa: TRY301

    except ModbusException as err:
        raise CannotConnect(f"Modbus connection failed: {err}") from err
    except Exception as err:
        raise CannotConnect(f"Unexpected connection error: {err}") from err
    finally:
        if client.connected:
            client.close()

    return {"title": f"KWB Modbus {data[CONF_HOST]}"}


class KwbModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KWB Modbus."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize Config flow."""
        self._connection_data: dict[str, Any] = {}
        self._modules_data: dict[str, Any] = {}
        # Queue of module keys that need instance selection
        self._pending_indexed_modules: list[str] = []
        # Module currently being configured
        self._current_indexed_module: str = ""
        # Accumulated instance selections: module_key → list of instance labels
        self._active_instances: dict[str, list[str]] = {}
        # Discovered (pre-selected) instances per module from Modbus scan
        self._discovered_indices: dict[str, list[str]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - Host and Port configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()

            try:
                await validate_connection(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._connection_data = user_input
                return await self.async_step_device()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device selection step."""
        if user_input is not None:
            self._connection_data[CONF_HEATING_DEVICE] = user_input[CONF_HEATING_DEVICE]
            return await self.async_step_modules()

        schema = vol.Schema(
            {
                vol.Required(CONF_HEATING_DEVICE): SelectSelector(
                    SelectSelectorConfig(
                        options=list(HEATING_DEVICES.keys()),
                        translation_key="heating_device",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="device", data_schema=schema)

    async def async_step_modules(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the add-on modules selection step."""
        if user_input is not None:
            self._modules_data = {
                CONF_ADDON_MODULES: user_input.get(CONF_ADDON_MODULES, []),
                CONF_EXPERT_MODE: user_input.get(CONF_EXPERT_MODE, False),
            }

            # Build queue of modules that have indexed SELECT_REGISTERS entries
            self._pending_indexed_modules = [
                m
                for m in self._modules_data[CONF_ADDON_MODULES]
                if _sorted_instances(m)
            ]
            self._active_instances = {}

            # Discover active instances via Modbus for each pending module
            host = self._connection_data[CONF_HOST]
            port = self._connection_data[CONF_PORT]
            slave_id = self._connection_data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
            self._discovered_indices = {}
            for module_key in self._pending_indexed_modules:
                self._discovered_indices[module_key] = (
                    await _discover_active_instances(host, port, slave_id, module_key)
                )

            return await self.async_step_module_instances()

        schema = vol.Schema(
            {
                vol.Optional(CONF_ADDON_MODULES, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=list(ADDON_MODULES.keys()),
                        translation_key="addon_modules",
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_EXPERT_MODE, default=False): bool,
            }
        )
        return self.async_show_form(step_id="modules", data_schema=schema)

    async def async_step_module_instances(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle instance selection for an indexed add-on module.

        This step is reused for each indexed module in sequence.
        Instances discovered via Modbus are pre-selected; the user can adjust.
        """
        if user_input is not None:
            self._active_instances[self._current_indexed_module] = user_input.get(
                "instances", []
            )

        if not self._pending_indexed_modules:
            return self._create_entry()

        self._current_indexed_module = self._pending_indexed_modules.pop(0)
        all_instances = _sorted_instances(self._current_indexed_module)
        discovered = self._discovered_indices.get(self._current_indexed_module, [])
        module_label = ADDON_MODULES.get(
            self._current_indexed_module, self._current_indexed_module
        )

        schema = vol.Schema(
            {
                vol.Optional("instances", default=discovered): SelectSelector(
                    SelectSelectorConfig(
                        options=all_instances,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="module_instances",
            data_schema=schema,
            description_placeholders={"module_name": module_label},
        )

    def _create_entry(self) -> ConfigFlowResult:
        """Create the config entry once all steps are complete."""
        heating_device = self._connection_data[CONF_HEATING_DEVICE]
        host = self._connection_data[CONF_HOST]
        title = f"KWB {HEATING_DEVICES[heating_device]} ({host})"
        return self.async_create_entry(
            title=title,
            data={
                **self._connection_data,
                CONF_ADDON_MODULES: self._modules_data[CONF_ADDON_MODULES],
                CONF_EXPERT_MODE: self._modules_data[CONF_EXPERT_MODE],
                CONF_ACTIVE_INSTANCES: self._active_instances,
                CONF_DISCOVERED_SENSORS: {},
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        if user_input is not None:
            try:
                await validate_connection(self.hass, user_input)
            except CannotConnect:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self.async_get_options_schema(config_entry.data),
                    errors={"base": "cannot_connect"},
                )
            except Exception:  # noqa: BLE001
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self.async_get_options_schema(config_entry.data),
                    errors={"base": "unknown"},
                )

            return self.async_update_reload_and_abort(
                config_entry,
                data_updates=user_input,
                reason="reconfigure_successful",
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.async_get_options_schema(config_entry.data),
        )

    def async_get_options_schema(self, current_data: dict[str, Any]) -> vol.Schema:
        """Get schema for reconfiguration with current values as defaults."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_data.get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_PORT, default=current_data.get(CONF_PORT, 502)
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=current_data.get(CONF_SCAN_INTERVAL, 1)
                ): vol.All(vol.Coerce(int)),
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
