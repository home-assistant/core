"""Home Assistant integration for indevolt device."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import IndevoltCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type IndevoltConfigEntry = ConfigEntry[IndevoltCoordinator]

_LOGGER = logging.getLogger(__name__)

# The map of Power Modes and associated API data points
MODE_MAP = {
    "self_consumed_prioritized": 1,
    "real_time_control": 4,
    "charge_discharge_schedule": 5,
}

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("power"): cv.positive_int,
    }
)

STOP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
    }
)

CHANGE_MODE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("mode"): vol.In(list(MODE_MAP.keys())),
    }
)

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]


async def _get_coordinator_from_device(
    hass: HomeAssistant, device_id: str
) -> IndevoltCoordinator:
    """Get coordinator from device ID."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)

    if not device_entry:
        raise ServiceValidationError(
            f"Device {device_id} not found",
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )

    entry_id = next(
        (entry_id for entry_id in device_entry.config_entries),
        None,
    )

    if not entry_id:
        raise ServiceValidationError(
            f"No config entry found for device {device_id}",
            translation_domain=DOMAIN,
            translation_key="no_config_entry",
        )

    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            f"Config entry for device {device_id} is not loaded",
            translation_domain=DOMAIN,
            translation_key="integration_not_loaded",
        )

    return entry.runtime_data


async def _switch_working_mode(
    coordinator: IndevoltCoordinator, target_mode: int
) -> bool:
    """Attempt to switch device to given working mode."""
    current_mode = coordinator.data.get("7101")

    if current_mode is None:
        mode_int = -1

    else:
        try:
            mode_int = (
                int(current_mode) if isinstance(current_mode, str) else current_mode
            )

        except (ValueError, TypeError):
            _LOGGER.warning("Invalid energy mode value: %s", current_mode)
            mode_int = -1

    _LOGGER.info("Current energy mode: %s", mode_int)

    if mode_int == 0:
        _LOGGER.error("Device is in Outdoor/Portable mode; cannot change working mode")
        return False

    if mode_int != target_mode:
        try:
            _LOGGER.info("Switching to energy mode: %s", target_mode)
            await coordinator.async_push_data("47005", target_mode)
            await coordinator.async_request_refresh()

        except Exception:
            _LOGGER.exception("Failed to switch to energy mode: %s", target_mode)
            return False

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Indevolt integration."""

    async def set_mode(call: ServiceCall) -> None:
        """Handle the service call to change the energy mode."""
        device_id = call.data[CONF_DEVICE_ID]
        mode_str = call.data["mode"]
        mode = MODE_MAP[mode_str]

        coordinator = await _get_coordinator_from_device(hass, device_id)
        await _switch_working_mode(coordinator, mode)

    async def charge(call: ServiceCall) -> None:
        """Handle the service call to start charging."""
        device_id = call.data[CONF_DEVICE_ID]
        power = call.data["power"]

        coordinator = await _get_coordinator_from_device(hass, device_id)

        # Validate power based on device generation
        generation = coordinator.config_entry.data.get("generation", 1)
        max_power = 2400 if generation == 2 else 1200
        if power > max_power:
            raise ServiceValidationError(
                f"Power {power}W exceeds maximum {max_power}W for generation {generation} devices"
            )

        # Ensure device is in Real-time Control mode
        if await _switch_working_mode(coordinator, 4):
            target_soc = coordinator.data.get("6002", 10)

            _LOGGER.info(
                "Charging %s with power: %s, target SOC: %s",
                device_id,
                power,
                target_soc,
            )
            await coordinator.async_push_data("47015", [1, power, target_soc])
            await coordinator.async_request_refresh()

    async def discharge(call: ServiceCall) -> None:
        """Handle the service call to start discharging."""
        device_id = call.data[CONF_DEVICE_ID]
        power = call.data["power"]

        coordinator = await _get_coordinator_from_device(hass, device_id)

        # Validate power based on device generation
        generation = coordinator.config_entry.data.get("generation", 1)
        max_power = 2400 if generation == 2 else 800
        if power > max_power:
            raise ServiceValidationError(
                f"Power {power}W exceeds maximum {max_power}W for generation {generation} devices"
            )

        # Ensure device is in Real-time Control mode
        if await _switch_working_mode(coordinator, 4):
            emergency_soc = coordinator.data.get("6105", 10)

            _LOGGER.info(
                "Discharging %s with power: %s, emergency SOC: %s",
                device_id,
                power,
                emergency_soc,
            )
            await coordinator.async_push_data("47015", [2, power, emergency_soc])
            await coordinator.async_request_refresh()

    async def stop(call: ServiceCall) -> None:
        """Handle the service call to stop the battery."""
        device_id = call.data[CONF_DEVICE_ID]

        coordinator = await _get_coordinator_from_device(hass, device_id)

        # Ensure device is in Real-time Control mode
        if await _switch_working_mode(coordinator, 4):
            _LOGGER.info("Stopping battery %s", device_id)
            await coordinator.async_push_data("47015", [0, 0, 0])
            await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "charge", charge, schema=SERVICE_SCHEMA)
    hass.services.async_register(DOMAIN, "discharge", discharge, schema=SERVICE_SCHEMA)
    hass.services.async_register(DOMAIN, "stop", stop, schema=STOP_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, "change_mode", set_mode, schema=CHANGE_MODE_SERVICE_SCHEMA
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Set up indevolt integration entry using given configuration."""
    try:
        # Setup coordinator and perform initial data refresh
        coordinator = IndevoltCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()

        # Store coordinator in runtime_data
        entry.runtime_data = coordinator

        # Setup platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    except Exception as err:
        _LOGGER.exception("Unexpected error occurred during initial setup")
        raise ConfigEntryNotReady from err

    else:
        return True


async def async_unload_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Unload a config entry and clean up resources (when integration is removed / reloaded)."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.async_shutdown()

    return unload_ok
