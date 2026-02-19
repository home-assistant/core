"""Home Assistant integration for indevolt device."""

from __future__ import annotations

from typing import Never

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, POWER_LIMITS, RT_MODE_KEY
from .coordinator import IndevoltConfigEntry, IndevoltCoordinator

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# The map of working Modes and associated API data points
MODE_MAP = {
    "self_consumed_prioritized": 1,
    "real_time_control": 4,
    "charge_discharge_schedule": 5,
}

SERVICE_SCHEMA = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
        vol.Required("target_soc"): cv.positive_int,
        vol.Required("power"): cv.positive_int,
    }
)

STOP_SERVICE_SCHEMA = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
    }
)

CHANGE_MODE_SERVICE_SCHEMA = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
        vol.Required("mode"): vol.In(list(MODE_MAP.keys())),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Set up indevolt integration entry using given configuration."""
    coordinator = IndevoltCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up indevolt services (actions)."""

    async def set_mode(call: ServiceCall) -> None:
        """Handle the service call to change the energy mode."""

        mode_str = call.data["mode"]
        mode = MODE_MAP[mode_str]

        errors: list[str] = []

        coordinators = await _async_get_coordinators_from_call(hass, call)
        for coordinator in coordinators:
            try:
                await coordinator.switch_energy_mode(mode)

            except (ServiceValidationError, HomeAssistantError) as err:
                errors.append(f"{coordinator.friendly_name}: {err}")

        if errors:
            raise ServiceValidationError("; ".join(errors))

    async def charge(call: ServiceCall) -> None:
        """Handle the service call to start charging."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        target_soc = call.data["target_soc"]
        power = call.data["power"]

        errors: list[str] = []

        for coordinator in coordinators:
            try:
                # Validate charge power based on device generation
                max_power = POWER_LIMITS[coordinator.generation]["max_charge_power"]
                if power > max_power:
                    _raise_power_exceeds_max(power, max_power, coordinator.generation)

                # Validate target SOC against emergency SOC threshold
                emergency_soc = coordinator.data.get("6105", 10)
                if target_soc < emergency_soc:
                    _raise_soc_below_emergency(target_soc, emergency_soc)

                # Ensure device is in Real-time Control mode and start charging
                if await coordinator.switch_energy_mode(MODE_MAP["real_time_control"]):
                    await coordinator.async_push_data(
                        RT_MODE_KEY, [1, power, target_soc]
                    )
                    await coordinator.async_request_refresh()

            except (ServiceValidationError, HomeAssistantError) as err:
                errors.append(f"{coordinator.friendly_name}: {err}")

        if errors:
            raise ServiceValidationError("; ".join(errors))

    async def discharge(call: ServiceCall) -> None:
        """Handle the service call to start discharging."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        power = call.data["power"]
        target_soc = call.data["target_soc"]

        errors: list[str] = []

        for coordinator in coordinators:
            try:
                # Validate discharge power based on device generation
                max_power = POWER_LIMITS[coordinator.generation]["max_discharge_power"]
                if power > max_power:
                    _raise_power_exceeds_max(power, max_power, coordinator.generation)

                # Validate target SOC against emergency SOC threshold
                emergency_soc = coordinator.data.get("6105", 10)
                if target_soc < emergency_soc:
                    _raise_soc_below_emergency(target_soc, emergency_soc)

                # Ensure device is in Real-time Control mode and start discharging
                if await coordinator.switch_energy_mode(MODE_MAP["real_time_control"]):
                    await coordinator.async_push_data(
                        RT_MODE_KEY, [2, power, target_soc]
                    )
                    await coordinator.async_request_refresh()

            except (ServiceValidationError, HomeAssistantError) as err:
                errors.append(f"{coordinator.friendly_name}: {err}")

        if errors:
            raise ServiceValidationError("; ".join(errors))

    async def stop(call: ServiceCall) -> None:
        """Handle the service call to stop the battery."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        errors: list[str] = []

        for coordinator in coordinators:
            try:
                # Ensure device is in Real-time Control mode and execute stop command
                if await coordinator.switch_energy_mode(MODE_MAP["real_time_control"]):
                    await coordinator.async_push_data(RT_MODE_KEY, [0, 0, 0])
                    await coordinator.async_request_refresh()

            except (ServiceValidationError, HomeAssistantError) as err:
                errors.append(f"{coordinator.friendly_name}: {err}")

        if errors:
            raise ServiceValidationError("; ".join(errors))

    hass.services.async_register(DOMAIN, "charge", charge, schema=SERVICE_SCHEMA)
    hass.services.async_register(DOMAIN, "discharge", discharge, schema=SERVICE_SCHEMA)
    hass.services.async_register(DOMAIN, "stop", stop, schema=STOP_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, "change_mode", set_mode, schema=CHANGE_MODE_SERVICE_SCHEMA
    )

    return True


async def _async_get_coordinators_from_call(
    hass: HomeAssistant,
    call: ServiceCall,
) -> list[IndevoltCoordinator]:
    """Resolve coordinator(s) targeted by a service call."""
    coordinators: list[IndevoltCoordinator] = []

    entry_ids = await async_extract_config_entry_ids(call)
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)

        # Validate domain of the entry
        if entry is None or entry.domain != DOMAIN:
            continue

        # Validate coordinator presence within entry
        if entry.runtime_data is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_ready",
                translation_placeholders={"entry_title": entry.title},
            )

        # Append to the result list
        coordinators.append(entry.runtime_data)

    if not coordinators:
        _raise_no_target_entries()

    return coordinators


async def async_unload_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Unload a config entry / clean up resources (when integration is removed / reloaded)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _raise_power_exceeds_max(power: int, max_power: int, generation: int) -> Never:
    """Raise a translated validation error for out-of-range power."""
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="power_exceeds_max",
        translation_placeholders={
            "power": str(power),
            "max_power": str(max_power),
            "generation": str(generation),
        },
    )


def _raise_soc_below_emergency(target: int, emergency_soc: int) -> Never:
    """Raise a translated validation error for out-of-range SOC."""
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="soc_below_emergency",
        translation_placeholders={
            "target": str(target),
            "emergency_soc": str(emergency_soc),
        },
    )


def _raise_no_target_entries() -> Never:
    """Raise a translated validation error for missing/invalid service targets."""
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_matching_target_entries",
    )
