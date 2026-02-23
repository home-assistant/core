"""Helpers for domestic hot water circulation boosts."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES,
    DEFAULT_DHW_BOOST_MIN_TEMPERATURE,
    DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES,
    DOMAIN,
)
from .types import ViCareDevice
from .utils import get_device_serial

_LOGGER = logging.getLogger(__name__)

_DAY_KEYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_DEFAULT_MAX_ENTRIES = 4
_DEFAULT_RESOLUTION_MINUTES = 10
_DEFAULT_MODE = "on"
_DEFAULT_DEFAULT_MODE = "off"
_BOOST_EVENT = "vicare_dhw_circulation_boost"


@dataclass(slots=True)
class DhwCirculationBoostState:
    """Track an active circulation boost."""

    original_schedule: dict[str, Any]
    restore_task: Any
    original_setpoint: float | None = None
    setpoint_changed: bool = False
    original_dhw_schedule: dict[str, Any] | None = None
    dhw_schedule_changed: bool = False
    warm_water_task: Any | None = None


@dataclass(slots=True)
class DhwHeatingPreparation:
    """Intermediate state for DHW heating preparation."""

    storage_temperature: float | None
    original_setpoint: float | None
    setpoint_changed: bool
    original_dhw_schedule: dict[str, Any] | None
    dhw_schedule_changed: bool


def _round_up_to_resolution(now: datetime, resolution: int) -> datetime | None:
    """Round time up to the next resolution boundary."""
    total_minutes = now.hour * 60 + now.minute
    rounded_minutes = ((total_minutes + resolution - 1) // resolution) * resolution
    if total_minutes % resolution == 0 and now.second == 0 and now.microsecond == 0:
        rounded_minutes += resolution
    if rounded_minutes >= 24 * 60:
        return None
    return now.replace(
        hour=rounded_minutes // 60,
        minute=rounded_minutes % 60,
        second=0,
        microsecond=0,
    )


def _format_time(value: datetime) -> str:
    """Return a HH:MM string for a datetime."""
    return f"{value.hour:02d}:{value.minute:02d}"


def _parse_time_to_minutes(value: str) -> int:
    """Return minutes from HH:MM."""
    return int(value[0:2]) * 60 + int(value[3:5])


def _sorted_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return entries sorted by start time."""
    return sorted(entries, key=lambda entry: _parse_time_to_minutes(entry["start"]))


def _with_positions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return entries with sequential positions."""
    return [
        {**entry, "position": position}
        for position, entry in enumerate(_sorted_entries(entries))
    ]


def _schedule_to_set_payload(
    schedule: dict[str, Any],
) -> dict[str, Any]:
    """Convert the read schedule to the set schedule payload."""
    payload: dict[str, Any] = {"defaultMode": schedule.get("default_mode")}
    for day in _DAY_KEYS:
        payload[day] = schedule.get(day, [])
    return payload


def _apply_boost_entry(
    entries: list[dict[str, Any]],
    start: datetime,
    end: datetime,
    max_entries: int,
    mode: str,
) -> list[dict[str, Any]]:
    """Return entries with a boost entry applied."""
    new_entry = {"start": _format_time(start), "end": _format_time(end), "mode": mode}
    current = _sorted_entries(entries)
    if len(current) >= max_entries:
        current[-1] = new_entry
    else:
        current.append(new_entry)
    return _with_positions(current)


def _get_schedule_constraints(
    raw_features: list[dict[str, Any]], feature_name: str
) -> dict[str, Any]:
    """Extract schedule constraints from raw features."""
    for feature in raw_features:
        if feature.get("feature") != feature_name:
            continue
        commands = feature.get("commands", {})
        constraints = (
            commands.get("setSchedule", {})
            .get("params", {})
            .get("newSchedule", {})
            .get("constraints", {})
        )
        return {
            "defaultMode": constraints.get("defaultMode", _DEFAULT_DEFAULT_MODE),
            "maxEntries": constraints.get("maxEntries", _DEFAULT_MAX_ENTRIES),
            "resolution": constraints.get("resolution", _DEFAULT_RESOLUTION_MINUTES),
            "modes": constraints.get("modes", [_DEFAULT_MODE]),
        }
    return {
        "defaultMode": _DEFAULT_DEFAULT_MODE,
        "maxEntries": _DEFAULT_MAX_ENTRIES,
        "resolution": _DEFAULT_RESOLUTION_MINUTES,
        "modes": [_DEFAULT_MODE],
    }


def _fire_boost_event(
    hass: HomeAssistant,
    *,
    stage: str,
    identifier: str,
    duration_minutes: int,
    min_boost_temperature: float,
    target_setpoint: float | None,
    heat_timeout_minutes: int,
    warm_water_delay_minutes: int,
    storage_temperature: float | None = None,
) -> None:
    """Emit a boost lifecycle event for automations."""
    hass.bus.async_fire(
        _BOOST_EVENT,
        {
            "stage": stage,
            "device_identifier": identifier,
            "duration_minutes": duration_minutes,
            "min_boost_temperature": min_boost_temperature,
            "target_setpoint": target_setpoint,
            "heat_timeout_minutes": heat_timeout_minutes,
            "warm_water_delay_minutes": warm_water_delay_minutes,
            "storage_temperature": storage_temperature,
        },
    )


async def _async_get_storage_temperature(
    hass: HomeAssistant, device: ViCareDevice
) -> float | None:
    """Return DHW storage temperature."""
    try:
        return await hass.async_add_executor_job(
            device.api.getDomesticHotWaterStorageTemperature
        )
    except PyViCareNotSupportedFeatureError as err:
        raise ServiceValidationError(
            "Domestic hot water storage temperature is not supported.",
            translation_domain=DOMAIN,
            translation_key="boost_storage_not_supported",
        ) from err


async def _async_get_target_setpoint(
    hass: HomeAssistant, device: ViCareDevice
) -> float | None:
    """Return configured DHW target setpoint."""
    try:
        return await hass.async_add_executor_job(
            device.api.getDomesticHotWaterConfiguredTemperature
        )
    except PyViCareNotSupportedFeatureError as err:
        raise ServiceValidationError(
            "Domestic hot water temperature is not supported.",
            translation_domain=DOMAIN,
            translation_key="boost_setpoint_not_supported",
        ) from err


async def _async_get_circulation_schedule(
    hass: HomeAssistant, device: ViCareDevice
) -> dict[str, Any]:
    """Return DHW circulation schedule."""
    try:
        schedule = await hass.async_add_executor_job(
            device.api.getDomesticHotWaterCirculationSchedule
        )
    except PyViCareNotSupportedFeatureError as err:
        raise ServiceValidationError(
            "Domestic hot water circulation schedule is not supported.",
            translation_domain=DOMAIN,
            translation_key="boost_not_supported",
        ) from err
    except PyViCareRateLimitError as err:
        raise HomeAssistantError(f"Vicare API rate limit exceeded: {err}") from err
    except PyViCareInvalidDataError as err:
        raise HomeAssistantError(f"Invalid data from Vicare server: {err}") from err
    except requests.exceptions.ConnectionError as err:
        raise HomeAssistantError("Unable to retrieve data from ViCare server") from err
    except ValueError as err:
        raise HomeAssistantError("Unable to decode data from ViCare server") from err

    if not isinstance(schedule, dict):
        raise ServiceValidationError(
            "Domestic hot water circulation schedule is not supported.",
            translation_domain=DOMAIN,
            translation_key="boost_not_supported",
        )

    return schedule


async def _async_restore_existing_boost(
    hass: HomeAssistant, device: ViCareDevice, existing: DhwCirculationBoostState
) -> None:
    """Restore state from an existing active boost."""
    existing.restore_task.cancel()
    if existing.warm_water_task is not None:
        existing.warm_water_task.cancel()
    await hass.async_add_executor_job(
        device.api.setDomesticHotWaterCirculationSchedule,
        existing.original_schedule,
    )
    if existing.setpoint_changed and existing.original_setpoint is not None:
        await hass.async_add_executor_job(
            device.api.setDomesticHotWaterTemperature,
            existing.original_setpoint,
        )
    if existing.dhw_schedule_changed and existing.original_dhw_schedule is not None:
        await hass.async_add_executor_job(
            device.api.setProperty,
            "heating.dhw.schedule",
            "setSchedule",
            {"newSchedule": existing.original_dhw_schedule},
        )


async def _async_prepare_heating_if_needed(
    hass: HomeAssistant,
    device: ViCareDevice,
    *,
    now: datetime,
    target_setpoint: float | None,
    min_boost_temperature: float,
    heat_timeout_minutes: int,
    warm_water_delay_minutes: int,
    duration_minutes: int,
    identifier: str,
    dhw_constraints: dict[str, Any],
) -> DhwHeatingPreparation:
    """Prepare DHW heating by raising setpoint and temporarily enabling schedule."""
    storage_temp = await _async_get_storage_temperature(hass, device)
    if storage_temp is not None and storage_temp >= min_boost_temperature:
        return DhwHeatingPreparation(
            storage_temperature=storage_temp,
            original_setpoint=None,
            setpoint_changed=False,
            original_dhw_schedule=None,
            dhw_schedule_changed=False,
        )

    _fire_boost_event(
        hass,
        stage="water_heating",
        identifier=identifier,
        duration_minutes=duration_minutes,
        min_boost_temperature=min_boost_temperature,
        target_setpoint=target_setpoint,
        heat_timeout_minutes=heat_timeout_minutes,
        warm_water_delay_minutes=warm_water_delay_minutes,
        storage_temperature=storage_temp,
    )

    original_setpoint: float | None = None
    setpoint_changed = False
    if target_setpoint is not None:
        original_setpoint = await _async_get_target_setpoint(hass, device)
        if original_setpoint is not None and target_setpoint > original_setpoint:
            await hass.async_add_executor_job(
                device.api.setDomesticHotWaterTemperature,
                target_setpoint,
            )
            setpoint_changed = True

    try:
        dhw_schedule = await hass.async_add_executor_job(
            device.api.getDomesticHotWaterSchedule
        )
    except PyViCareNotSupportedFeatureError as err:
        raise ServiceValidationError(
            "Domestic hot water schedule is not supported.",
            translation_domain=DOMAIN,
            translation_key="boost_dhw_schedule_not_supported",
        ) from err

    if not isinstance(dhw_schedule, dict):
        raise ServiceValidationError(
            "Domestic hot water schedule is not supported.",
            translation_domain=DOMAIN,
            translation_key="boost_dhw_schedule_not_supported",
        )

    original_dhw_schedule = _schedule_to_set_payload(dhw_schedule)
    original_dhw_schedule["defaultMode"] = dhw_constraints.get(
        "defaultMode", _DEFAULT_DEFAULT_MODE
    )
    dhw_schedule_payload = copy.deepcopy(original_dhw_schedule)
    dhw_resolution = int(dhw_constraints["resolution"])
    dhw_max_entries = int(dhw_constraints["maxEntries"])
    dhw_mode = dhw_constraints.get("modes", [_DEFAULT_MODE])[0]
    dhw_start = _round_up_to_resolution(now, dhw_resolution)
    if dhw_start is None:
        raise ServiceValidationError(
            "Boost duration runs past midnight.",
            translation_domain=DOMAIN,
            translation_key="boost_too_late",
        )
    dhw_end = dhw_start + timedelta(minutes=heat_timeout_minutes)
    if dhw_end.date() != dhw_start.date():
        raise ServiceValidationError(
            "Boost duration runs past midnight.",
            translation_domain=DOMAIN,
            translation_key="boost_too_late",
        )

    dhw_day_key = _DAY_KEYS[dhw_start.weekday()]
    dhw_day_entries = list(dhw_schedule_payload.get(dhw_day_key, []))
    dhw_schedule_payload[dhw_day_key] = _apply_boost_entry(
        dhw_day_entries, dhw_start, dhw_end, dhw_max_entries, dhw_mode
    )
    await hass.async_add_executor_job(
        device.api.setProperty,
        "heating.dhw.schedule",
        "setSchedule",
        {"newSchedule": dhw_schedule_payload},
    )
    try:
        timeout_seconds = heat_timeout_minutes * 60
        elapsed = 0
        while elapsed < timeout_seconds:
            storage_temp = await _async_get_storage_temperature(hass, device)
            if storage_temp is not None and storage_temp >= min_boost_temperature:
                break
            await asyncio.sleep(60)
            elapsed += 60
    finally:
        await hass.async_add_executor_job(
            device.api.setProperty,
            "heating.dhw.schedule",
            "setSchedule",
            {"newSchedule": original_dhw_schedule},
        )
    return DhwHeatingPreparation(
        storage_temperature=storage_temp,
        original_setpoint=original_setpoint,
        setpoint_changed=setpoint_changed,
        original_dhw_schedule=original_dhw_schedule,
        dhw_schedule_changed=True,
    )


async def _get_device_identifier(hass: HomeAssistant, device: ViCareDevice) -> str:
    """Return the device identifier used in the device registry."""
    gateway_serial = device.config.getConfig().serial
    device_id = device.config.getId()
    device_serial = await hass.async_add_executor_job(get_device_serial, device.api)
    return (
        f"{gateway_serial}_{device_serial.replace('-', '_')}"
        if device_serial is not None
        else f"{gateway_serial}_{device_id}"
    )


async def async_get_device_from_call(
    hass: HomeAssistant,
    devices: list[ViCareDevice],
    entity_id: str | None,
    device_id: str | None,
) -> ViCareDevice:
    """Return the ViCare device selected in the service call."""
    if not entity_id and not device_id:
        if len(devices) == 1:
            return devices[0]
        raise ServiceValidationError(
            "Select a device for this service call.",
            translation_domain=DOMAIN,
            translation_key="boost_device_required",
        )

    if entity_id:
        entity_entry = er.async_get(hass).async_get(entity_id)
        if entity_entry is None or entity_entry.device_id is None:
            raise ServiceValidationError(
                "Entity is not linked to a device.",
                translation_domain=DOMAIN,
                translation_key="boost_entity_no_device",
            )
        device_id = entity_entry.device_id

    if device_id is None:
        raise ServiceValidationError(
            "Select a device for this service call.",
            translation_domain=DOMAIN,
            translation_key="boost_device_required",
        )

    device_entry = dr.async_get(hass).async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(
            "Device does not exist.",
            translation_domain=DOMAIN,
            translation_key="boost_device_missing",
        )

    identifiers = device_entry.identifiers
    device_map: dict[str, ViCareDevice] = {}
    for device in devices:
        identifier = await _get_device_identifier(hass, device)
        device_map[identifier] = device

    for domain, identifier in identifiers:
        if domain != DOMAIN:
            continue
        if matched_device := device_map.get(identifier):
            return matched_device

    raise ServiceValidationError(
        "Selected device is not managed by ViCare.",
        translation_domain=DOMAIN,
        translation_key="boost_device_not_found",
    )


async def async_activate_dhw_circulation_boost(
    hass: HomeAssistant,
    device: ViCareDevice,
    duration_minutes: int,
    state_map: dict[str, DhwCirculationBoostState],
    *,
    min_boost_temperature: float | None = None,
    min_storage_temperature: float | None = None,
    target_setpoint: float | None = None,
    heat_timeout_minutes: int | None = None,
    warm_water_delay_minutes: int | None = None,
) -> None:
    """Activate a temporary DHW circulation boost."""
    identifier = await _get_device_identifier(hass, device)
    now = dt_util.now()
    effective_min_boost_temperature = (
        min_boost_temperature
        if min_boost_temperature is not None
        else (
            min_storage_temperature
            if min_storage_temperature is not None
            else DEFAULT_DHW_BOOST_MIN_TEMPERATURE
        )
    )
    effective_heat_timeout_minutes = (
        heat_timeout_minutes
        if heat_timeout_minutes is not None and heat_timeout_minutes > 0
        else DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES
    )
    effective_warm_water_delay_minutes = (
        warm_water_delay_minutes
        if warm_water_delay_minutes is not None and warm_water_delay_minutes > 0
        else DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES
    )

    try:
        raw_features = await hass.async_add_executor_job(device.config.get_raw_json)
    except requests.exceptions.ConnectionError, ValueError, PyViCareInvalidDataError:
        _LOGGER.debug("Unable to fetch raw features for circulation constraints")
        raw_features = {"data": []}

    raw_data = raw_features.get("data", [])
    circulation_constraints = _get_schedule_constraints(
        raw_data, "heating.dhw.pumps.circulation.schedule"
    )
    dhw_constraints = _get_schedule_constraints(raw_data, "heating.dhw.schedule")
    resolution = int(circulation_constraints["resolution"])
    max_entries = int(circulation_constraints["maxEntries"])
    mode = circulation_constraints.get("modes", [_DEFAULT_MODE])[0]

    if duration_minutes % resolution != 0:
        duration_minutes = (
            (duration_minutes + resolution - 1) // resolution
        ) * resolution

    if existing := state_map.get(identifier):
        await _async_restore_existing_boost(hass, device, existing)

    _fire_boost_event(
        hass,
        stage="boost_initiated",
        identifier=identifier,
        duration_minutes=duration_minutes,
        min_boost_temperature=effective_min_boost_temperature,
        target_setpoint=target_setpoint,
        heat_timeout_minutes=effective_heat_timeout_minutes,
        warm_water_delay_minutes=effective_warm_water_delay_minutes,
    )

    schedule = await _async_get_circulation_schedule(hass, device)

    original_schedule = _schedule_to_set_payload(schedule)
    original_schedule["defaultMode"] = circulation_constraints.get(
        "defaultMode", _DEFAULT_DEFAULT_MODE
    )
    heating_prep = await _async_prepare_heating_if_needed(
        hass,
        device,
        now=now,
        target_setpoint=target_setpoint,
        min_boost_temperature=effective_min_boost_temperature,
        heat_timeout_minutes=effective_heat_timeout_minutes,
        warm_water_delay_minutes=effective_warm_water_delay_minutes,
        duration_minutes=duration_minutes,
        identifier=identifier,
        dhw_constraints=dhw_constraints,
    )

    now = dt_util.now()
    start = _round_up_to_resolution(now, resolution)
    if start is None:
        raise ServiceValidationError(
            "Boost duration runs past midnight.",
            translation_domain=DOMAIN,
            translation_key="boost_too_late",
        )
    end = start + timedelta(minutes=duration_minutes)
    if end.date() != start.date():
        raise ServiceValidationError(
            "Boost duration runs past midnight.",
            translation_domain=DOMAIN,
            translation_key="boost_too_late",
        )

    schedule_payload = copy.deepcopy(original_schedule)
    day_key = _DAY_KEYS[start.weekday()]
    day_entries = list(schedule_payload.get(day_key, []))
    schedule_payload[day_key] = _apply_boost_entry(
        day_entries, start, end, max_entries, mode
    )

    await hass.async_add_executor_job(
        device.api.setDomesticHotWaterCirculationSchedule,
        schedule_payload,
    )
    _fire_boost_event(
        hass,
        stage="water_circulation_started",
        identifier=identifier,
        duration_minutes=duration_minutes,
        min_boost_temperature=effective_min_boost_temperature,
        target_setpoint=target_setpoint,
        heat_timeout_minutes=effective_heat_timeout_minutes,
        warm_water_delay_minutes=effective_warm_water_delay_minutes,
        storage_temperature=heating_prep.storage_temperature,
    )

    async def _warm_water_available() -> None:
        """Fire warm water available event after configured delay."""
        await asyncio.sleep(
            timedelta(minutes=effective_warm_water_delay_minutes).total_seconds()
        )
        _fire_boost_event(
            hass,
            stage="warm_water_available",
            identifier=identifier,
            duration_minutes=duration_minutes,
            min_boost_temperature=effective_min_boost_temperature,
            target_setpoint=target_setpoint,
            heat_timeout_minutes=effective_heat_timeout_minutes,
            warm_water_delay_minutes=effective_warm_water_delay_minutes,
        )

    warm_water_task = hass.async_create_task(_warm_water_available())

    async def _restore_schedule() -> None:
        try:
            await asyncio.sleep(timedelta(minutes=duration_minutes).total_seconds())
            await hass.async_add_executor_job(
                device.api.setDomesticHotWaterCirculationSchedule,
                original_schedule,
            )
            if (
                heating_prep.setpoint_changed
                and heating_prep.original_setpoint is not None
            ):
                await hass.async_add_executor_job(
                    device.api.setDomesticHotWaterTemperature,
                    heating_prep.original_setpoint,
                )
            if (
                heating_prep.dhw_schedule_changed
                and heating_prep.original_dhw_schedule is not None
            ):
                await hass.async_add_executor_job(
                    device.api.setProperty,
                    "heating.dhw.schedule",
                    "setSchedule",
                    {"newSchedule": heating_prep.original_dhw_schedule},
                )
        except (
            requests.exceptions.ConnectionError,
            PyViCareInvalidDataError,
            ValueError,
        ) as err:
            _LOGGER.error("Unable to restore DHW circulation schedule: %s", err)
        except PyViCareRateLimitError as err:
            _LOGGER.error("Vicare API rate limit exceeded: %s", err)
        finally:
            state_map.pop(identifier, None)

    restore_task = hass.async_create_task(_restore_schedule())
    state_map[identifier] = DhwCirculationBoostState(
        original_schedule=original_schedule,
        restore_task=restore_task,
        original_setpoint=heating_prep.original_setpoint,
        setpoint_changed=heating_prep.setpoint_changed,
        original_dhw_schedule=heating_prep.original_dhw_schedule,
        dhw_schedule_changed=heating_prep.dhw_schedule_changed,
        warm_water_task=warm_water_task,
    )
