"""Services for Indevolt integration."""

from __future__ import annotations

import asyncio
from typing import Final, Never

from indevolt_api import (
    IndevoltRealtimeAction,
    PowerExceedsMaxError,
    SocBelowMinimumError,
)
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import IndevoltCoordinator

RT_ACTION_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required("device_id"): vol.All(
            cv.ensure_list,
            [cv.string],
        ),
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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Indevolt integration."""

    async def charge(call: ServiceCall) -> None:
        """Handle the service call to start charging."""
        await _async_handle_realtime_action(hass, call, IndevoltRealtimeAction.CHARGE)

    async def discharge(call: ServiceCall) -> None:
        """Handle the service call to start discharging."""
        await _async_handle_realtime_action(
            hass, call, IndevoltRealtimeAction.DISCHARGE
        )

    hass.services.async_register(
        DOMAIN, "charge", charge, schema=RT_ACTION_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "discharge", discharge, schema=RT_ACTION_SERVICE_SCHEMA
    )


async def _async_handle_realtime_action(
    hass: HomeAssistant,
    call: ServiceCall,
    action: IndevoltRealtimeAction,
) -> None:
    """Validate and execute a realtime action for one or more coordinators."""
    coordinators = await _async_get_coordinators_from_call(hass, call)

    power: int = call.data["power"]
    target_soc: int = call.data["target_soc"]

    _validate_realtime_action(coordinators, action, power, target_soc)
    await _execute_realtime_action(coordinators, action, power, target_soc)


async def _async_get_coordinators_from_call(
    hass: HomeAssistant,
    call: ServiceCall,
) -> list[IndevoltCoordinator]:
    """Resolve coordinator(s) targeted by a service call."""
    entry_ids = await async_extract_config_entry_ids(call)

    coordinators: list[IndevoltCoordinator] = [
        entry.runtime_data
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if entry.entry_id in entry_ids
    ]

    if not coordinators:
        _raise_no_target_entries()

    return coordinators


def _validate_realtime_action(
    coordinators: list[IndevoltCoordinator],
    action: IndevoltRealtimeAction,
    power: int,
    target_soc: int,
) -> None:
    """Validate parameters prior to calling `_execute_realtime_action`."""

    errors: list[str] = []

    for coordinator in coordinators:
        try:
            try:
                match action:
                    case IndevoltRealtimeAction.CHARGE:
                        coordinator.api.check_charge_limits(
                            power, target_soc, coordinator.generation
                        )
                    case IndevoltRealtimeAction.DISCHARGE:
                        coordinator.api.check_discharge_limits(
                            power, target_soc, coordinator.generation
                        )

            except PowerExceedsMaxError as err:
                _raise_power_exceeds_max(err.power, err.max_power, err.generation)

            except SocBelowMinimumError as err:
                _raise_soc_below_minimum(err.target_soc, err.minimum_soc)

            # Validate target SOC against known emergency SOC (soft limit)
            emergency_soc = coordinator.get_emergency_soc()
            if target_soc < emergency_soc:
                _raise_soc_below_emergency(target_soc, emergency_soc)

        except ServiceValidationError as err:
            if len(coordinators) == 1:
                raise

            errors.append(f"{coordinator.friendly_name}: {err}")

    if errors:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="multi_device_errors",
            translation_placeholders={"errors": "; ".join(errors)},
        )


async def _execute_realtime_action(
    coordinators: list[IndevoltCoordinator],
    action: IndevoltRealtimeAction,
    power: int,
    target_soc: int,
) -> None:
    """Execute async_execute_realtime_action on all coordinators concurrently."""
    results: list[None | BaseException] = await asyncio.gather(
        *(
            coordinator.async_realtime_action(action, power, target_soc)
            for coordinator in coordinators
        ),
        return_exceptions=True,
    )

    errors: list[str] = []

    for coordinator, result in zip(coordinators, results, strict=True):
        if isinstance(result, BaseException):
            if len(coordinators) == 1 or not isinstance(result, Exception):
                raise result

            errors.append(f"{coordinator.friendly_name}: {result}")

    if errors:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="multi_device_errors",
            translation_placeholders={"errors": "; ".join(errors)},
        )


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


def _raise_soc_below_minimum(target_soc: int, minimum_soc: int) -> Never:
    """Raise a translated validation error when SOC is below the device's hard minimum."""
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="soc_below_minimum",
        translation_placeholders={
            "target": str(target_soc),
            "minimum_soc": str(minimum_soc),
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
