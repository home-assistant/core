"""Services for the Sofar integration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from modbus_connection import ModbusError
from sofar_modbus.modern.enums import FeedinLimitationMode, PassiveModeTimeoutAction
import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    async_get_config_entry,
    async_register_admin_service,
)

from .const import DOMAIN
from .coordinator import SofarConfigEntry

SERVICE_SET_ACTIVE_POWER_LIMIT = "set_active_power_limit"
SERVICE_SET_FEED_IN_LIMIT = "set_feed_in_limit"
SERVICE_SET_PASSIVE_MODE_POWER = "set_passive_mode_power"
SERVICE_SET_PASSIVE_MODE_TIMEOUT = "set_passive_mode_timeout"

ATTR_ACTION = "action"
ATTR_BATTERY_POWER_MAX = "battery_power_max"
ATTR_BATTERY_POWER_MIN = "battery_power_min"
ATTR_ENABLED = "enabled"
ATTR_GRID_POWER = "grid_power"
ATTR_LIMIT = "limit"
ATTR_MAX_POWER = "max_power"
ATTR_TIMEOUT = "timeout"

_ENTRY_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str})

SET_FEED_IN_LIMIT_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        vol.Required(ATTR_MODE): vol.In(
            [mode.name.lower() for mode in FeedinLimitationMode]
        ),
        vol.Required(ATTR_MAX_POWER): cv.positive_int,
    }
)

SET_ACTIVE_POWER_LIMIT_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        vol.Required(ATTR_ENABLED): cv.boolean,
        vol.Required(ATTR_LIMIT): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
    }
)

SET_PASSIVE_MODE_TIMEOUT_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        vol.Required(ATTR_TIMEOUT): cv.positive_int,
        vol.Required(ATTR_ACTION): vol.In(
            [action.name.lower() for action in PassiveModeTimeoutAction]
        ),
    }
)

SET_PASSIVE_MODE_POWER_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        vol.Required(ATTR_GRID_POWER): int,
        vol.Required(ATTR_BATTERY_POWER_MIN): int,
        vol.Required(ATTR_BATTERY_POWER_MAX): int,
    }
)


def _get_entry(
    hass: HomeAssistant, call: ServiceCall, component: str
) -> SofarConfigEntry:
    """Return a loaded entry whose inverter serves the needed registers."""
    entry: SofarConfigEntry = async_get_config_entry(
        hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    if component not in entry.runtime_data.served_components:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unsupported_action",
            translation_placeholders={"title": entry.title},
        )
    return entry


@asynccontextmanager
async def _writing(entry: SofarConfigEntry) -> AsyncIterator[None]:
    """Translate a failed write, then let the settings sensors catch up."""
    try:
        yield
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_action_value",
            translation_placeholders={"error": str(err)},
        ) from err
    except ModbusError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="modbus_error",
            translation_placeholders={"error": str(err)},
        ) from err
    await entry.runtime_data.settings.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Sofar services."""

    async def _handle_set_feed_in_limit(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "feed_in")
        device = entry.runtime_data.readings.device
        mode = FeedinLimitationMode[call.data[ATTR_MODE].upper()]
        async with _writing(entry):
            await device.feed_in.async_write_limit(mode, call.data[ATTR_MAX_POWER])

    async def _handle_set_active_power_limit(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "active_power_control")
        device = entry.runtime_data.readings.device
        async with _writing(entry):
            await device.active_power_control.async_write_active_power_limit(
                call.data[ATTR_ENABLED], call.data[ATTR_LIMIT]
            )

    async def _handle_set_passive_mode_timeout(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "passive")
        device = entry.runtime_data.readings.device
        action = PassiveModeTimeoutAction[call.data[ATTR_ACTION].upper()]
        async with _writing(entry):
            await device.passive.async_write_timeout(call.data[ATTR_TIMEOUT], action)

    async def _handle_set_passive_mode_power(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "passive")
        device = entry.runtime_data.readings.device
        async with _writing(entry):
            await device.passive.async_write_power(
                call.data[ATTR_GRID_POWER],
                call.data[ATTR_BATTERY_POWER_MIN],
                call.data[ATTR_BATTERY_POWER_MAX],
            )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_FEED_IN_LIMIT,
        _handle_set_feed_in_limit,
        schema=SET_FEED_IN_LIMIT_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_ACTIVE_POWER_LIMIT,
        _handle_set_active_power_limit,
        schema=SET_ACTIVE_POWER_LIMIT_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_PASSIVE_MODE_TIMEOUT,
        _handle_set_passive_mode_timeout,
        schema=SET_PASSIVE_MODE_TIMEOUT_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_PASSIVE_MODE_POWER,
        _handle_set_passive_mode_power,
        schema=SET_PASSIVE_MODE_POWER_SCHEMA,
    )
