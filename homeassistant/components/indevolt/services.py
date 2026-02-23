"""Services for Indevolt integration."""

from __future__ import annotations

import asyncio
from typing import Never

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .const import DOMAIN, ENERGY_MODES, POWER_LIMITS
from .coordinator import IndevoltCoordinator

CHARGE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("target"): cv.ensure_list,
        vol.Required("target_soc"): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, max=100),
        ),
        vol.Required("power"): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=2400),
        ),
    }
)

STOP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("target"): cv.ensure_list,
    }
)

CHANGE_MODE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("target"): cv.ensure_list,
        vol.Required("energy_mode"): vol.In(list(ENERGY_MODES.keys())),
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Indevolt integration."""

    async def set_mode(call: ServiceCall) -> None:
        """Handle the service call to change the energy mode."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        mode_str = call.data["energy_mode"]
        mode = ENERGY_MODES[mode_str]

        await asyncio.gather(
            *(
                coordinator.async_switch_energy_mode(mode)
                for coordinator in coordinators
            )
        )

    async def charge(call: ServiceCall) -> None:
        """Handle the service call to start charging."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        target_soc = call.data["target_soc"]
        power = call.data["power"]

        errors: list[str] = []

        # Perform validations
        for coordinator in coordinators:
            try:
                # Validate charge power based on device generation
                max_power = POWER_LIMITS[coordinator.generation]["max_charge_power"]
                if power > max_power:
                    _raise_power_exceeds_max(power, max_power, coordinator.generation)

                # Validate target SOC against emergency SOC threshold
                emergency_soc = await coordinator.async_get_emergency_soc()
                if target_soc < emergency_soc:
                    _raise_soc_below_emergency(target_soc, emergency_soc)

            except ServiceValidationError as err:
                errors.append(f"{coordinator.friendly_name}: {err}")

        if errors:
            raise ServiceValidationError("; ".join(errors))

        # Perform actions
        await asyncio.gather(
            *(
                coordinator.async_execute_realtime_action([1, power, target_soc])
                for coordinator in coordinators
            )
        )

    async def discharge(call: ServiceCall) -> None:
        """Handle the service call to start discharging."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        power = call.data["power"]
        target_soc = call.data["target_soc"]

        errors: list[str] = []

        # Perform validations
        for coordinator in coordinators:
            try:
                # Validate discharge power based on device generation
                max_power = POWER_LIMITS[coordinator.generation]["max_discharge_power"]
                if power > max_power:
                    _raise_power_exceeds_max(power, max_power, coordinator.generation)

                # Validate target SOC against emergency SOC threshold
                emergency_soc = await coordinator.async_get_emergency_soc()
                if target_soc < emergency_soc:
                    _raise_soc_below_emergency(target_soc, emergency_soc)

            except ServiceValidationError as err:
                errors.append(f"{coordinator.friendly_name}: {err}")

        if errors:
            raise ServiceValidationError("; ".join(errors))

        # Perform actions
        await asyncio.gather(
            *(
                coordinator.async_execute_realtime_action([2, power, target_soc])
                for coordinator in coordinators
            )
        )

    async def stop(call: ServiceCall) -> None:
        """Handle the service call to stop the battery."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        # Perform actions
        await asyncio.gather(
            *(
                coordinator.async_execute_realtime_action([0, 0, 0])
                for coordinator in coordinators
            )
        )

    hass.services.async_register(DOMAIN, "stop", stop, schema=STOP_SERVICE_SCHEMA)
    hass.services.async_register(DOMAIN, "charge", charge, schema=CHARGE_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, "discharge", discharge, schema=CHARGE_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "change_energy_mode", set_mode, schema=CHANGE_MODE_SERVICE_SCHEMA
    )


async def _async_get_coordinators_from_call(
    hass: HomeAssistant,
    call: ServiceCall,
) -> list[IndevoltCoordinator]:
    """Resolve coordinator(s) targeted by a service call."""
    coordinators: list[IndevoltCoordinator] = []

    # Ensure targets are provided by user
    device_ids: list[str] = call.data.get("target") or []
    if not device_ids:
        _raise_no_target_entries()

    device_registry = dr.async_get(hass)
    for device_id in device_ids:
        # Retrieve device from registry
        device = device_registry.async_get(device_id)
        if device is None:
            continue

        for entry_id in device.config_entries:
            # Validate domain of the entry
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain != DOMAIN:
                continue

            # Validate coordinator presence within entry
            if entry.runtime_data is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="config_entry_not_ready",
                    translation_placeholders={"entry_title": entry.title},
                )

            # Append to the result list (found it)
            if entry.runtime_data not in coordinators:
                coordinators.append(entry.runtime_data)

    if not coordinators:
        _raise_no_target_entries()

    return coordinators


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
