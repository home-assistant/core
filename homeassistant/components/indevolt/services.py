"""Services for Indevolt integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Never

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .const import DOMAIN, POWER_LIMITS
from .coordinator import IndevoltConfigEntry, IndevoltCoordinator

_LOGGER = logging.getLogger(__name__)


CHARGE_SERVICE_SCHEMA = vol.Schema(
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

STOP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("device_ids"): vol.All(
            cv.ensure_list,
            [cv.string],
        ),
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Indevolt integration."""

    async def charge(call: ServiceCall) -> None:
        """Handle the service call to start charging."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        target_soc: int = call.data["target_soc"]
        power: int = call.data["power"]

        errors: list[str] = []

        # Perform validations
        for coordinator in coordinators:
            try:
                # Validate charge power based on device generation
                max_power: int = POWER_LIMITS[coordinator.generation][
                    "max_charge_power"
                ]
                if power > max_power:
                    _raise_power_exceeds_max(power, max_power, coordinator.generation)

                # Validate target SOC against emergency SOC threshold
                emergency_soc = coordinator.async_get_emergency_soc()
                if target_soc < emergency_soc:
                    _raise_soc_below_emergency(target_soc, emergency_soc)

            except ServiceValidationError as err:
                if len(coordinators) == 1:
                    raise

                errors.append(f"{coordinator.friendly_name}: {err}")

        if errors:
            raise ServiceValidationError("; ".join(errors))

        # Perform actions & process results
        await _execute_realtime_action(coordinators, 1, power, target_soc)

    async def discharge(call: ServiceCall) -> None:
        """Handle the service call to start discharging."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        power: int = call.data["power"]
        target_soc: int = call.data["target_soc"]

        errors: list[str] = []

        # Perform validations
        for coordinator in coordinators:
            try:
                # Validate discharge power based on device generation
                max_power: int = POWER_LIMITS[coordinator.generation][
                    "max_discharge_power"
                ]
                if power > max_power:
                    _raise_power_exceeds_max(power, max_power, coordinator.generation)

                # Validate target SOC against emergency SOC threshold
                emergency_soc = coordinator.async_get_emergency_soc()
                if target_soc < emergency_soc:
                    _raise_soc_below_emergency(target_soc, emergency_soc)

            except ServiceValidationError as err:
                if len(coordinators) == 1:
                    raise

                errors.append(f"{coordinator.friendly_name}: {err}")

        if errors:
            raise ServiceValidationError("; ".join(errors))

        # Perform actions & process results
        await _execute_realtime_action(coordinators, 2, power, target_soc)

    async def stop(call: ServiceCall) -> None:
        """Handle the service call to stop the battery."""
        coordinators = await _async_get_coordinators_from_call(hass, call)

        # Perform actions & process results
        await _execute_realtime_action(coordinators, 0, 0, 0)

    hass.services.async_register(DOMAIN, "stop", stop, schema=STOP_SERVICE_SCHEMA)
    hass.services.async_register(DOMAIN, "charge", charge, schema=CHARGE_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, "discharge", discharge, schema=CHARGE_SERVICE_SCHEMA
    )


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


async def _execute_realtime_action(
    coordinators: list[IndevoltCoordinator],
    action_code: int,
    power: int,
    target_soc: int,
) -> None:
    """Execute async_execute_realtime_action on all coordinators concurrently."""
    results: list[None | BaseException] = await asyncio.gather(
        *(
            coordinator.async_execute_realtime_action([action_code, power, target_soc])
            for coordinator in coordinators
        ),
        return_exceptions=True,
    )

    exception: BaseException | None = None
    for coordinator, result in zip(coordinators, results, strict=True):
        if isinstance(result, BaseException):
            _LOGGER.error(
                "Coordinator %s failed: %s", coordinator.friendly_name, result
            )
            if exception is None:
                exception = result

    if exception:
        if len(coordinators) == 1:
            raise exception

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_failed",
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
