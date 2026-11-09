"""Services for the Sofar integration."""

from collections.abc import Awaitable
from enum import StrEnum

from modbus_connection import ModbusError
import probatio
from sofar_modbus.modern.enums import FeedinLimitationMode, PassiveModeTimeoutAction

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    async_get_config_entry,
    async_register_admin_service,
)

from .const import DOMAIN
from .coordinator import SofarConfigEntry


class SofarService(StrEnum):
    """Store keys for Sofar services."""

    SET_ACTIVE_POWER_LIMIT = "set_active_power_limit"
    SET_BATTERY_CUTOFFS = "set_battery_cutoffs"
    SET_FEED_IN_LIMIT = "set_feed_in_limit"
    SET_PASSIVE_MODE_POWER = "set_passive_mode_power"
    SET_PASSIVE_MODE_TIMEOUT = "set_passive_mode_timeout"


class SofarServiceArgument(StrEnum):
    """Store keys for Sofar service arguments."""

    ACTION = "action"
    BATTERY_POWER_MAX = "battery_power_max"
    BATTERY_POWER_MIN = "battery_power_min"
    CHARGE_CUTOFF_SOC = "charge_cutoff_soc"
    ENABLED = "enabled"
    GRID_POWER = "grid_power"
    LIMIT = "limit"
    MAX_POWER = "max_power"
    MODE = "mode"
    OFF_GRID_DISCHARGE_CUTOFF_SOC = "off_grid_discharge_cutoff_soc"
    OFF_GRID_RECOVERY_SOC = "off_grid_recovery_soc"
    ON_GRID_DISCHARGE_CUTOFF_SOC = "on_grid_discharge_cutoff_soc"
    TIMEOUT = "timeout"


_ENTRY_SCHEMA = probatio.Schema(
    {probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str}
)

# The selectors in services.yaml only bound the UI, not a scripted call.
_POWER_RANGE = probatio.All(int, probatio.Range(min=-100000, max=100000))

SET_FEED_IN_LIMIT_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        probatio.Required(SofarServiceArgument.MODE): probatio.In(
            [mode.name.lower() for mode in FeedinLimitationMode]
        ),
        # Not cv.positive_int: it would let 3000.9 pass as 3000.
        probatio.Required(SofarServiceArgument.MAX_POWER): probatio.All(
            probatio.Coerce(float), probatio.Range(min=0, max=100000)
        ),
    }
)

SET_ACTIVE_POWER_LIMIT_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        probatio.Required(SofarServiceArgument.ENABLED): cv.boolean,
        probatio.Required(SofarServiceArgument.LIMIT): probatio.All(
            probatio.Coerce(float), probatio.Percentage()
        ),
    }
)

SET_PASSIVE_MODE_TIMEOUT_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        probatio.Required(SofarServiceArgument.TIMEOUT): probatio.All(
            cv.positive_int, probatio.Range(max=65535)
        ),
        probatio.Required(SofarServiceArgument.ACTION): probatio.In(
            [action.name.lower() for action in PassiveModeTimeoutAction]
        ),
    }
)

SET_PASSIVE_MODE_POWER_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        probatio.Required(SofarServiceArgument.GRID_POWER): _POWER_RANGE,
        probatio.Required(SofarServiceArgument.BATTERY_POWER_MIN): _POWER_RANGE,
        probatio.Required(SofarServiceArgument.BATTERY_POWER_MAX): _POWER_RANGE,
    }
)

SET_BATTERY_CUTOFFS_SCHEMA = _ENTRY_SCHEMA.extend(
    {
        probatio.Required(
            SofarServiceArgument.ON_GRID_DISCHARGE_CUTOFF_SOC
        ): probatio.All(int, probatio.Range(min=10, max=100)),
        probatio.Required(
            SofarServiceArgument.OFF_GRID_DISCHARGE_CUTOFF_SOC
        ): probatio.All(int, probatio.Range(min=10, max=30)),
        probatio.Required(SofarServiceArgument.OFF_GRID_RECOVERY_SOC): probatio.All(
            int, probatio.Range(min=15, max=100)
        ),
        probatio.Optional(SofarServiceArgument.CHARGE_CUTOFF_SOC): probatio.All(
            int, probatio.Range(min=60, max=100)
        ),
    }
)


def _get_entry(
    hass: HomeAssistant, call: ServiceCall, component: str
) -> SofarConfigEntry:
    """Return a loaded entry whose inverter serves the needed registers."""
    entry: SofarConfigEntry = async_get_config_entry(
        hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    if component not in entry.runtime_data.served_components:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unsupported_action",
            translation_placeholders={"title": entry.title},
        )
    return entry


async def _write(entry: SofarConfigEntry, write: Awaitable[None]) -> None:
    """Translate a failed write, then let the settings sensors catch up."""
    try:
        await write
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_action_value",
        ) from err
    except ModbusError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="write_failed",
        ) from err
    await entry.runtime_data.settings.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Sofar services."""

    async def _handle_set_feed_in_limit(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "feed_in")
        device = entry.runtime_data.readings.device
        max_power = call.data[SofarServiceArgument.MAX_POWER]
        if max_power % 100:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="max_power_not_a_multiple_of_100",
            )
        await _write(
            entry,
            device.feed_in.async_write_limit(
                FeedinLimitationMode[call.data[SofarServiceArgument.MODE].upper()],
                int(max_power),
            ),
        )

    async def _handle_set_active_power_limit(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "active_power_control")
        device = entry.runtime_data.readings.device
        await _write(
            entry,
            device.active_power_control.async_write_active_power_limit(
                call.data[SofarServiceArgument.ENABLED],
                call.data[SofarServiceArgument.LIMIT],
            ),
        )

    async def _handle_set_passive_mode_timeout(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "passive")
        device = entry.runtime_data.readings.device
        await _write(
            entry,
            device.passive.async_write_timeout(
                call.data[SofarServiceArgument.TIMEOUT],
                PassiveModeTimeoutAction[
                    call.data[SofarServiceArgument.ACTION].upper()
                ],
            ),
        )

    async def _handle_set_passive_mode_power(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "passive")
        device = entry.runtime_data.readings.device
        await _write(
            entry,
            device.passive.async_write_power(
                call.data[SofarServiceArgument.GRID_POWER],
                call.data[SofarServiceArgument.BATTERY_POWER_MIN],
                call.data[SofarServiceArgument.BATTERY_POWER_MAX],
            ),
        )

    async def _handle_set_battery_cutoffs(call: ServiceCall) -> None:
        entry = _get_entry(hass, call, "battery_config")
        if (
            SofarServiceArgument.CHARGE_CUTOFF_SOC in call.data
            and "battery_charge_cutoff" not in entry.runtime_data.served_components
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="charge_cutoff_unsupported",
                translation_placeholders={"title": entry.title},
            )
        await _write(
            entry,
            entry.runtime_data.readings.device.async_write_battery_cutoffs(
                call.data[SofarServiceArgument.ON_GRID_DISCHARGE_CUTOFF_SOC],
                call.data[SofarServiceArgument.OFF_GRID_DISCHARGE_CUTOFF_SOC],
                call.data[SofarServiceArgument.OFF_GRID_RECOVERY_SOC],
                call.data.get(SofarServiceArgument.CHARGE_CUTOFF_SOC),
            ),
        )

    async_register_admin_service(
        hass,
        DOMAIN,
        SofarService.SET_FEED_IN_LIMIT,
        _handle_set_feed_in_limit,
        schema=SET_FEED_IN_LIMIT_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SofarService.SET_ACTIVE_POWER_LIMIT,
        _handle_set_active_power_limit,
        schema=SET_ACTIVE_POWER_LIMIT_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SofarService.SET_PASSIVE_MODE_TIMEOUT,
        _handle_set_passive_mode_timeout,
        schema=SET_PASSIVE_MODE_TIMEOUT_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SofarService.SET_PASSIVE_MODE_POWER,
        _handle_set_passive_mode_power,
        schema=SET_PASSIVE_MODE_POWER_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SofarService.SET_BATTERY_CUTOFFS,
        _handle_set_battery_cutoffs,
        schema=SET_BATTERY_CUTOFFS_SCHEMA,
    )
