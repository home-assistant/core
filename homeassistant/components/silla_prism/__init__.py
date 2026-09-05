"""silla_prism_async."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BATTERY_DISCHARGE_POSITIVE,
    CONF_BATTERY_MAX_CHARGE_POWER,
    CONF_BATTERY_POWER_SENSOR,
    CONF_BATTERY_SOC_SENSOR,
    CONF_HOME_LOAD_INCLUDES_EV,
    CONF_HOME_LOAD_POWER_SENSOR,
    CONF_MAX_CURRENT,
    CONF_PORTS,
    CONF_POWERWALL,
    CONF_SERIAL,
    CONF_SOLAR_BALANCE_DEADBAND_POWER,
    CONF_SOLAR_BALANCE_DECREASE_STEP,
    CONF_SOLAR_BALANCE_DRY_RUN,
    CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER,
    CONF_SOLAR_BALANCE_INCREASE_INTERVAL,
    CONF_SOLAR_BALANCE_INCREASE_STEP,
    CONF_SOLAR_BALANCE_MID_RESERVE_POWER,
    CONF_SOLAR_BALANCE_PHASES,
    CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
    CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
    CONF_SOLAR_BALANCE_SOC_HIGH,
    CONF_SOLAR_BALANCE_SOC_MID,
    CONF_SOLAR_BALANCE_START_DELAY,
    CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER,
    CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE,
    CONF_SOLAR_BATTERY_BALANCE,
    CONF_SOLAR_PRODUCTION_POWER_SENSOR,
    CONF_TOPIC,
    CONF_VSENSORS,
    DEFAULT_BATTERY_DISCHARGE_POSITIVE,
    DEFAULT_BATTERY_MAX_CHARGE_POWER,
    DEFAULT_BATTERY_POWER_SENSOR,
    DEFAULT_BATTERY_SOC_SENSOR,
    DEFAULT_HOME_LOAD_INCLUDES_EV,
    DEFAULT_HOME_LOAD_POWER_SENSOR,
    DEFAULT_MAX_CURRENT,
    DEFAULT_PORTS,
    DEFAULT_POWERWALL,
    DEFAULT_SERIAL,
    DEFAULT_SOLAR_BALANCE_DEADBAND_POWER,
    DEFAULT_SOLAR_BALANCE_DECREASE_STEP,
    DEFAULT_SOLAR_BALANCE_DRY_RUN,
    DEFAULT_SOLAR_BALANCE_HIGH_RESERVE_POWER,
    DEFAULT_SOLAR_BALANCE_INCREASE_INTERVAL,
    DEFAULT_SOLAR_BALANCE_INCREASE_STEP,
    DEFAULT_SOLAR_BALANCE_MID_RESERVE_POWER,
    DEFAULT_SOLAR_BALANCE_PHASES,
    DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
    DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
    DEFAULT_SOLAR_BALANCE_SOC_HIGH,
    DEFAULT_SOLAR_BALANCE_SOC_MID,
    DEFAULT_SOLAR_BALANCE_START_DELAY,
    DEFAULT_SOLAR_BALANCE_TARGET_EXPORT_POWER,
    DEFAULT_SOLAR_BALANCE_USE_BATTERY_CHARGE,
    DEFAULT_SOLAR_BATTERY_BALANCE,
    DEFAULT_SOLAR_PRODUCTION_POWER_SENSOR,
    DEFAULT_VSENSORS,
    DOMAIN,
)
from .coordinator import PrismCoordinator
from .entry_data import RuntimeEntryData

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Silla Prism integration."""
    return True


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


def _get_device_identifier(port: int, serial: str) -> str:
    if serial == "" and port == 0:
        return "prism"
    if serial == "":
        return f"PrismPort{port}"
    return f"Prism_Port{port}_Serial{serial}"


def _get_device_name(port: int, serial: str) -> str:
    if serial == "" and port == 0:
        return "Prism"
    if serial == "":
        return f"Prism Port {port}"
    return f"Prism Serial {serial} Port {port}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Silla Prism component."""
    _topic = entry.data[CONF_TOPIC].rstrip("/") + "/"
    _ports = entry.data.get(CONF_PORTS, DEFAULT_PORTS)
    _serial = entry.data.get(CONF_SERIAL, DEFAULT_SERIAL)
    _vsensors = entry.data.get(CONF_VSENSORS, DEFAULT_VSENSORS)
    _powerwall = entry.data.get(CONF_POWERWALL, DEFAULT_POWERWALL)
    _maxcurr = entry.data.get(CONF_MAX_CURRENT, DEFAULT_MAX_CURRENT)
    _solar_battery_balance = entry.data.get(
        CONF_SOLAR_BATTERY_BALANCE, DEFAULT_SOLAR_BATTERY_BALANCE
    )
    _battery_power_sensor = entry.data.get(
        CONF_BATTERY_POWER_SENSOR, DEFAULT_BATTERY_POWER_SENSOR
    )
    _solar_production_power_sensor = entry.data.get(
        CONF_SOLAR_PRODUCTION_POWER_SENSOR,
        DEFAULT_SOLAR_PRODUCTION_POWER_SENSOR,
    )
    _home_load_power_sensor = entry.data.get(
        CONF_HOME_LOAD_POWER_SENSOR, DEFAULT_HOME_LOAD_POWER_SENSOR
    )
    _home_load_includes_ev = entry.data.get(
        CONF_HOME_LOAD_INCLUDES_EV, DEFAULT_HOME_LOAD_INCLUDES_EV
    )
    _battery_soc_sensor = entry.data.get(
        CONF_BATTERY_SOC_SENSOR, DEFAULT_BATTERY_SOC_SENSOR
    )
    _battery_discharge_positive = entry.data.get(
        CONF_BATTERY_DISCHARGE_POSITIVE, DEFAULT_BATTERY_DISCHARGE_POSITIVE
    )
    _battery_max_charge_power = entry.data.get(
        CONF_BATTERY_MAX_CHARGE_POWER, DEFAULT_BATTERY_MAX_CHARGE_POWER
    )
    _solar_balance_phases = entry.data.get(
        CONF_SOLAR_BALANCE_PHASES, DEFAULT_SOLAR_BALANCE_PHASES
    )
    _solar_balance_start_delay = entry.data.get(
        CONF_SOLAR_BALANCE_START_DELAY, DEFAULT_SOLAR_BALANCE_START_DELAY
    )
    _solar_balance_use_battery_charge = entry.data.get(
        CONF_SOLAR_BALANCE_USE_BATTERY_CHARGE,
        DEFAULT_SOLAR_BALANCE_USE_BATTERY_CHARGE,
    )
    _solar_balance_soc_mid = entry.data.get(
        CONF_SOLAR_BALANCE_SOC_MID, DEFAULT_SOLAR_BALANCE_SOC_MID
    )
    _solar_balance_soc_high = entry.data.get(
        CONF_SOLAR_BALANCE_SOC_HIGH, DEFAULT_SOLAR_BALANCE_SOC_HIGH
    )
    _solar_balance_mid_reserve_power = entry.data.get(
        CONF_SOLAR_BALANCE_MID_RESERVE_POWER,
        DEFAULT_SOLAR_BALANCE_MID_RESERVE_POWER,
    )
    _solar_balance_high_reserve_power = entry.data.get(
        CONF_SOLAR_BALANCE_HIGH_RESERVE_POWER,
        DEFAULT_SOLAR_BALANCE_HIGH_RESERVE_POWER,
    )
    _solar_balance_target_export_power = entry.data.get(
        CONF_SOLAR_BALANCE_TARGET_EXPORT_POWER,
        DEFAULT_SOLAR_BALANCE_TARGET_EXPORT_POWER,
    )
    _solar_balance_deadband_power = entry.data.get(
        CONF_SOLAR_BALANCE_DEADBAND_POWER,
        DEFAULT_SOLAR_BALANCE_DEADBAND_POWER,
    )
    _solar_balance_increase_interval = entry.data.get(
        CONF_SOLAR_BALANCE_INCREASE_INTERVAL,
        DEFAULT_SOLAR_BALANCE_INCREASE_INTERVAL,
    )
    _solar_balance_increase_step = entry.data.get(
        CONF_SOLAR_BALANCE_INCREASE_STEP,
        DEFAULT_SOLAR_BALANCE_INCREASE_STEP,
    )
    _solar_balance_decrease_step = entry.data.get(
        CONF_SOLAR_BALANCE_DECREASE_STEP,
        DEFAULT_SOLAR_BALANCE_DECREASE_STEP,
    )
    _solar_balance_residual_export_power = entry.data.get(
        CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
        DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_POWER,
    )
    _solar_balance_residual_export_delay = entry.data.get(
        CONF_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
        DEFAULT_SOLAR_BALANCE_RESIDUAL_EXPORT_DELAY,
    )
    _solar_balance_dry_run = entry.data.get(
        CONF_SOLAR_BALANCE_DRY_RUN,
        DEFAULT_SOLAR_BALANCE_DRY_RUN,
    )
    _devices_info = []
    _devices_info.append(
        DeviceInfo(
            identifiers={(DOMAIN, _get_device_identifier(0, _serial))},
            name=_get_device_name(0, _serial),
            manufacturer="Silla",
            model="Prism",
            serial_number=_serial,
        )
    )

    _devices_info.extend(
        [
            DeviceInfo(
                identifiers={(DOMAIN, _get_device_identifier(port, _serial))},
                name=_get_device_name(port, _serial),
                manufacturer="Silla",
                model="Prism",
                serial_number=_serial,
            )
            for port in range(1, _ports + 1)
        ]
    )

    entry_data = RuntimeEntryData(
        topic=_topic,
        ports=_ports,
        serial=_serial,
        vsensors=_vsensors,
        powerwall=_powerwall,
        maxcurr=_maxcurr,
        solar_battery_balance=_solar_battery_balance,
        battery_power_sensor=_battery_power_sensor,
        solar_production_power_sensor=_solar_production_power_sensor,
        home_load_power_sensor=_home_load_power_sensor,
        home_load_includes_ev=_home_load_includes_ev,
        battery_soc_sensor=_battery_soc_sensor,
        battery_discharge_positive=_battery_discharge_positive,
        battery_max_charge_power=_battery_max_charge_power,
        solar_balance_phases=_solar_balance_phases,
        solar_balance_start_delay=_solar_balance_start_delay,
        solar_balance_use_battery_charge=_solar_balance_use_battery_charge,
        solar_balance_soc_mid=_solar_balance_soc_mid,
        solar_balance_soc_high=_solar_balance_soc_high,
        solar_balance_mid_reserve_power=_solar_balance_mid_reserve_power,
        solar_balance_high_reserve_power=_solar_balance_high_reserve_power,
        solar_balance_target_export_power=_solar_balance_target_export_power,
        solar_balance_deadband_power=_solar_balance_deadband_power,
        solar_balance_increase_interval=_solar_balance_increase_interval,
        solar_balance_increase_step=_solar_balance_increase_step,
        solar_balance_decrease_step=_solar_balance_decrease_step,
        solar_balance_residual_export_power=_solar_balance_residual_export_power,
        solar_balance_residual_export_delay=_solar_balance_residual_export_delay,
        solar_balance_dry_run=_solar_balance_dry_run,
        devices=_devices_info,
        coordinator=PrismCoordinator(hass, entry),
    )
    entry.runtime_data = entry_data
    await entry_data.coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
