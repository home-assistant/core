"""DataUpdateCoordinator for the Life360 integration."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from life360 import Life360, Life360Error, LoginError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LENGTH_FEET,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DistanceConverter
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    COMM_MAX_RETRIES,
    COMM_TIMEOUT,
    CONF_AUTHORIZATION,
    DOMAIN,
    LOGGER,
    SPEED_DIGITS,
    SPEED_FACTOR_MPH,
    UPDATE_INTERVAL,
)


class MissingLocReason(Enum):
    """Reason member location information is missing."""

    VAGUE_ERROR_REASON = "vague error reason"
    EXPLICIT_ERROR_REASON = "explicit error reason"


@dataclass
class Life360Place:
    """Life360 Place data."""

    name: str
    latitude: float
    longitude: float
    radius: float


@dataclass
class Life360Circle:
    """Life360 Circle data."""

    name: str
    places: dict[str, Life360Place]


@dataclass
class Life360Member:
    """Life360 Member data."""

    address: str | None
    at_loc_since: datetime
    battery_charging: bool
    battery_level: int
    driving: bool
    entity_picture: str
    gps_accuracy: int
    last_seen: datetime
    latitude: float
    longitude: float
    name: str
    place: str | None
    speed: float
    wifi_on: bool


@dataclass
class Life360Data:
    """Life360 data."""

    circles: dict[str, Life360Circle] = field(init=False, default_factory=dict)
    members: dict[str, Life360Member] = field(init=False, default_factory=dict)


class Life360DataUpdateCoordinator(DataUpdateCoordinator[Life360Data]):
    """Life360 data update coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize data update coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} ({entry.unique_id})",
            update_interval=UPDATE_INTERVAL,
        )
        self._hass = hass
        self._api = Life360(
            session=async_get_clientsession(hass),
            timeout=COMM_TIMEOUT,
            max_retries=COMM_MAX_RETRIES,
            authorization=entry.data[CONF_AUTHORIZATION],
        )
        self._missing_loc_reason = hass.data[DOMAIN].missing_loc_reason

    async def _retrieve_data(self, func: str, *args: Any) -> list[dict[str, Any]]:
        """Get data from Life360."""
        try:
            return await getattr(self._api, func)(*args)
        except LoginError as exc:
            LOGGER.debug("Login error: %s", exc)
            raise ConfigEntryAuthFailed(exc) from exc
        except Life360Error as exc:
            LOGGER.debug("%s: %s", exc.__class__.__name__, exc)
            raise UpdateFailed(exc) from exc

    async def _async_update_data(self) -> Life360Data:
        """Get & process data from Life360."""

        data = Life360Data()

        for circle in await self._retrieve_data("get_circles"):
            circle_id = circle["id"]
            circle_members = await self._retrieve_data("get_circle_members", circle_id)
            circle_places = await self._retrieve_data("get_circle_places", circle_id)

            data.circles[circle_id] = Life360Circle(
                circle["name"],
                {
                    place["id"]: Life360Place(
                        place["name"],
                        float(place["latitude"]),
                        float(place["longitude"]),
                        float(place["radius"]),
                    )
                    for place in circle_places
                },
            )

            for member in circle_members:
                # Member isn't sharing location.
                if not int(member["features"]["shareLocation"]):
                    continue

                member_id = member["id"]

                first = member["firstName"]
                last = member["lastName"]
                if first and last:
                    name = " ".join([first, last])
                else:
                    name = first or last

                cur_missing_reason = self._missing_loc_reason.get(member_id)

                # Check if location information is missing. This can happen if server
                # has not heard from member's device in a long time (e.g., has been off
                # for a long time, or has lost service, etc.)
                if loc := member["location"]:
                    with suppress(KeyError):
                        del self._missing_loc_reason[member_id]
                else:
                    if explicit_reason := member["issues"]["title"]:
                        if extended_reason := member["issues"]["dialog"]:
                            explicit_reason += f": {extended_reason}"
                    # Note that different Circles can report missing location in
                    # different ways. E.g., one might report an explicit reason and
                    # another does not. If a vague reason has already been logged but a
                    # more explicit reason is now available, log that, too.
                    if (
                        cur_missing_reason is None
                        or cur_missing_reason == MissingLocReason.VAGUE_ERROR_REASON
                        and explicit_reason
                    ):
                        if explicit_reason:
                            self._missing_loc_reason[
                                member_id
                            ] = MissingLocReason.EXPLICIT_ERROR_REASON
                            err_msg = explicit_reason
                        else:
                            self._missing_loc_reason[
                                member_id
                            ] = MissingLocReason.VAGUE_ERROR_REASON
                            err_msg = "Location information missing"
                        LOGGER.error("%s: %s", name, err_msg)
                    continue

                # Note that member may be in more than one circle. If that's the case
                # just go ahead and process the newly retrieved data (overwriting the
                # older data), since it might be slightly newer than what was retrieved
                # while processing another circle.

                place = loc["name"] or None

                address1: str | None = loc["address1"] or None
                address2: str | None = loc["address2"] or None
                if address1 and address2:
                    address: str | None = ", ".join([address1, address2])
                else:
                    address = address1 or address2

                speed = max(0, float(loc["speed"]) * SPEED_FACTOR_MPH)
                if self._hass.config.units is METRIC_SYSTEM:
                    speed = DistanceConverter.convert(
                        speed, LENGTH_MILES, LENGTH_KILOMETERS
                    )

                data.members[member_id] = Life360Member(
                    address,
                    dt_util.utc_from_timestamp(int(loc["since"])),
                    bool(int(loc["charge"])),
                    int(float(loc["battery"])),
                    bool(int(loc["isDriving"])),
                    member["avatar"],
                    # Life360 reports accuracy in feet, but Device Tracker expects
                    # gps_accuracy in meters.
                    round(
                        DistanceConverter.convert(
                            float(loc["accuracy"]), LENGTH_FEET, LENGTH_METERS
                        )
                    ),
                    dt_util.utc_from_timestamp(int(loc["timestamp"])),
                    float(loc["latitude"]),
                    float(loc["longitude"]),
                    name,
                    place,
                    round(speed, SPEED_DIGITS),
                    bool(int(loc["wifiState"])),
                )

        return data
