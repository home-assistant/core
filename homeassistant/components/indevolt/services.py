"""Services for Indevolt integration."""

from __future__ import annotations

import asyncio
from typing import Final, Never

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .const import DOMAIN, POWER_LIMITS, RealtimeAction
from .coordinator import IndevoltConfigEntry, IndevoltCoordinator

RT_ACTION_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required("device_ids"): vol.All(
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
        await _async_handle_realtime_action(
            hass,
            call,
            RealtimeAction.CHARGE,
            power_key="max_charge_power",
        )

    async def discharge(call: ServiceCall) -> None:
        """Handle the service call to start discharging."""
        await _async_handle_realtime_action(
            hass,
            call,
            RealtimeAction.DISCHARGE,
            power_key="max_discharge_power",
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
    action_code: RealtimeAction,
    power_key: str,
) -> None:
    """Validate and execute a realtime action for one or more coordinators."""
    coordinators = await _async_get_coordinators_from_call(hass, call)

    power: int = call.data["power"]
    target_soc: int = call.data["target_soc"]

    _validate_realtime_action(
        coordinators,
        power,
        target_soc,
        power_key=power_key,
    )

    await _execute_realtime_action(coordinators, action_code, power, target_soc)


async def _async_get_coordinators_from_call(
    hass: HomeAssistant,
    call: ServiceCall,
) -> list[IndevoltCoordinator]:
    """Resolve coordinator(s) targeted by a service call."""
    coordinators: list[IndevoltCoordinator] = []

    # Ensure targets are provided by user
    device_ids: list[str] = call.data.get("device_ids") or []
    if not device_ids:
        _raise_no_target_entries()

    loaded_entries: dict[str, IndevoltConfigEntry] = {
        entry.entry_id: entry
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
    }

    device_registry = dr.async_get(hass)
    for device_id in device_ids:
        # Retrieve device from registry
        device = device_registry.async_get(device_id)
        if device is None:
            continue

        for entry_id in device.config_entries:
            # Check whether entry is loaded
            if entry_id not in loaded_entries:
                continue

            entry = loaded_entries[entry_id]

            # Append to the result list (found it)
            if entry.runtime_data not in coordinators:
                coordinators.append(entry.runtime_data)

    if not coordinators:
        _raise_no_target_entries()

    return coordinators


def _validate_realtime_action(
    coordinators: list[IndevoltCoordinator],
    power: int,
    target_soc: int,
    power_key: str,
) -> None:
    """Validates parameters prior to calling async_execute_realtime_action."""

    errors: list[str] = []

    for coordinator in coordinators:
        try:
            # Validate (dis)charge power based on device generation
            max_power: int = POWER_LIMITS[coordinator.generation][power_key]
            if power > max_power:
                _raise_power_exceeds_max(power, max_power, coordinator.generation)

            # Validate target SOC against emergency SOC threshold
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
    action_code: RealtimeAction,
    power: int,
    target_soc: int,
) -> None:
    """Execute async_execute_realtime_action on all coordinators concurrently."""
    results: list[None | BaseException] = await asyncio.gather(
        *(
            coordinator.async_execute_realtime_action(
                [action_code.value, power, target_soc]
            )
            for coordinator in coordinators
        ),
        return_exceptions=True,
    )

    errors: list[str] = []

    for coordinator, result in zip(coordinators, results, strict=True):
        if isinstance(result, BaseException):
            if isinstance(
                result, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)
            ):
                raise result

            if len(coordinators) == 1:
                raise result

            errors.append(f"{coordinator.friendly_name}: {result}")

    if errors:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="multi_device_errors",
            translation_placeholders={"errors": "; ".join(errors)},
        ) from exception


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
