"""The MELCloud Climate integration."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from http import HTTPStatus

import aiohttp
from aiohttp import ClientConnectionError, ClientResponseError
from pymelcloud import DEVICE_TYPE_ATW, get_devices
from pymelcloud import AtwDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]

DOMAIN = "melcloud"

# Service name
SERVICE_SET_HOLIDAY_MODE = "set_holiday_mode"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"

SET_HOLIDAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.positive_int,
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_END_DATE): cv.date,
    }
)

MELCLOUD_BASE_URL = "https://app.melcloud.com/Mitsubishi.Wifi.Client"


async def _async_get_building_timezone(
    session: aiohttp.ClientSession, token: str, building_id: int
) -> int:
    """Fetch building TimeZone from MelCloud User/ListDevices.

    The TimeZone ID is building-level metadata needed for the HolidayMode/Update
    payload. It is not surfaced by pymelcloud's device confs, so we fetch it here.
    Returns 0 (UTC) as a safe fallback if not found.
    """
    try:
        async with asyncio.timeout(10):
            resp = await session.get(
                f"{MELCLOUD_BASE_URL}/User/ListDevices",
                headers={"X-MitsContextKey": token},
            )
            resp.raise_for_status()
            entries = await resp.json()
    except (aiohttp.ClientError, TimeoutError):
        return 0

    for entry in entries:
        if entry.get("ID") == building_id or entry.get("BuildingID") == building_id:
            return entry.get("TimeZone", 0)
        # Also check nested structure
        structure = entry.get("Structure", {})
        if structure.get("ID") == building_id:
            return structure.get("TimeZone", 0)

    return 0


async def _async_set_holiday_mode(
    hass: HomeAssistant,
    token: str,
    building_id: int,
    start_date: date | None,
    end_date: date | None,
) -> None:
    """Call the MelCloud HolidayMode/Update API endpoint.

    Endpoint confirmed via browser traffic interception:
        POST /Mitsubishi.Wifi.Client/HolidayMode/Update

    IMPORTANT: StartDate/EndDate must be DateTimeComponents objects (Year/Month/Day/
    Hour/Minute/Second), NOT ISO strings. The API returns HTTP 200 for both formats
    but silently ignores ISO strings without saving. Confirmed by intercepting actual
    browser traffic from the MELCloud web app.

    Payload (enabled):
        {
            "Enabled": true,
            "StartDate": {"Year": 2026, "Month": 3, "Day": 6, "Hour": 9, "Minute": 0, "Second": 0},
            "EndDate":   {"Year": 2026, "Month": 5, "Day": 6, "Hour": 23, "Minute": 59, "Second": 0},
            "HMTimeZones": [{"TimeZone": 118, "Buildings": [872887],
                             "Floors": [], "Areas": [], "Devices": []}],
            "SkipPage1": true
        }

    To disable: Enabled=false, StartDate=null, EndDate=null.
    """
    session = async_get_clientsession(hass)
    enabled = end_date is not None

    # Fetch building timezone (needed for HMTimeZones payload)
    building_tz = await _async_get_building_timezone(session, token, building_id)

    def _date_components(d: date, *, hour: int = 0, minute: int = 0) -> dict:
        """Convert a date to MelCloud DateTimeComponents format.

        The API requires this object format — ISO strings are silently ignored.
        """
        return {
            "Year": d.year,
            "Month": d.month,
            "Day": d.day,
            "Hour": hour,
            "Minute": minute,
            "Second": 0,
        }

    payload = {
        "Enabled": enabled,
        "StartDate": _date_components(start_date) if enabled and start_date else None,
        "EndDate": _date_components(end_date, hour=23, minute=59) if enabled and end_date else None,
        "HMTimeZones": [
            {
                "TimeZone": building_tz,
                "Buildings": [building_id],
                "Floors": [],
                "Areas": [],
                "Devices": [],
            }
        ],
        "SkipPage1": True,
    }

    try:
        async with asyncio.timeout(10):
            resp = await session.post(
                f"{MELCLOUD_BASE_URL}/HolidayMode/Update",
                json=payload,
                headers={"X-MitsContextKey": token},
            )
            resp.raise_for_status()
            # API returns empty body on success (Enabled=true) or JSON on disable
            text = await resp.text()
            result = None
            if text.strip():
                try:
                    import json as _json
                    result = _json.loads(text)
                except ValueError:
                    pass
    except (aiohttp.ClientError, TimeoutError) as err:
        raise ServiceValidationError(
            f"Failed to contact MelCloud API: {err}"
        ) from err

    if isinstance(result, dict) and not result.get("Success", True):
        raise ServiceValidationError(
            f"MelCloud returned failure: {result.get('GlobalErrors') or result}"
        )


async def async_setup_entry(hass: HomeAssistant, entry: MelCloudConfigEntry) -> bool:
    """Establish connection with MELCloud."""
    try:
        async with asyncio.timeout(10):
            all_devices = await get_devices(
                token=entry.data[CONF_TOKEN],
                session=async_get_clientsession(hass),
                conf_update_interval=timedelta(minutes=30),
                device_set_debounce=timedelta(seconds=2),
            )
    except ClientResponseError as ex:
        if ex.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise ConfigEntryAuthFailed from ex
        if ex.status == HTTPStatus.TOO_MANY_REQUESTS:
            raise UpdateFailed(
                "MELCloud rate limit exceeded. Your account may be temporarily blocked"
            ) from ex
        raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex
    except (TimeoutError, ClientConnectionError) as ex:
        raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex

    # Create per-device coordinators
    coordinators: dict[str, list[MelCloudDeviceUpdateCoordinator]] = {}
    device_registry = dr.async_get(hass)
    for device_type, devices in all_devices.items():
        coordinators[device_type] = [
            MelCloudDeviceUpdateCoordinator(hass, device, entry) for device in devices
        ]

        await asyncio.gather(
            *(
                coordinator.async_config_entry_first_refresh()
                for coordinator in coordinators[device_type]
            )
        )

        for coordinator in coordinators[device_type]:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                **coordinator.device_info,
            )

    entry.runtime_data = coordinators

    # Register set_holiday_mode service (ATW devices only — holiday mode is a
    # building-level setting that requires start/end dates, not a simple toggle)
    async def handle_set_holiday_mode(call: ServiceCall) -> None:
        """Handle the set_holiday_mode service call."""
        device_id: int = call.data["device_id"]
        start_date: date | None = call.data.get(ATTR_START_DATE)
        end_date: date | None = call.data.get(ATTR_END_DATE)

        # Validate: if enabling, both dates required
        if end_date is not None and start_date is None:
            raise ServiceValidationError(
                "start_date is required when end_date is provided"
            )
        if end_date is not None and start_date is not None and start_date > end_date:
            raise ServiceValidationError(
                "start_date must be before end_date"
            )

        # Find the ATW device and its building_id
        atw_coordinators = entry.runtime_data.get(DEVICE_TYPE_ATW, [])
        coordinator = next(
            (c for c in atw_coordinators if c.device.device_id == device_id),
            None,
        )
        if coordinator is None:
            raise ServiceValidationError(
                f"No ATW device found with device_id {device_id}"
            )

        building_id: int = coordinator.device.building_id
        token: str = entry.data[CONF_TOKEN]

        await _async_set_holiday_mode(hass, token, building_id, start_date, end_date)
        # Refresh device state to reflect holiday mode change
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOLIDAY_MODE,
        handle_set_holiday_mode,
        schema=SET_HOLIDAY_MODE_SCHEMA,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

