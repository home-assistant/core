"""DataUpdateCoordinator for the Life360 integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.distance import convert
import homeassistant.util.dt as dt_util

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

    # Don't include address field in eq comparison because it often changes (back and
    # forth) between updates. If it was included there would be way more state changes
    # and database updates than is useful.
    address: str | None = field(compare=False)
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


class Life360DataUpdateCoordinator(DataUpdateCoordinator):
    """Life360 data update coordinator."""

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
            timeout=COMM_TIMEOUT,
            max_retries=COMM_MAX_RETRIES,
            authorization=entry.data[CONF_AUTHORIZATION],
        )

    async def _retrieve_data(self, func: str, *args: Any) -> list[dict[str, Any]]:
        """Get data from Life360."""
        try:
            return await self._hass.async_add_executor_job(
                getattr(self._api, func), *args
            )
        except LoginError as exc:
            LOGGER.debug("Login error: %s", exc)
            raise ConfigEntryAuthFailed from exc
        except Life360Error as exc:
            LOGGER.debug("%s: %s", exc.__class__.__name__, exc)
            raise UpdateFailed from exc

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

                # Note that member may be in more than one circle. If that's the case just
                # go ahead and process the newly retrieved data (overwriting the older
                # data), since it might be slightly newer than what was retrieved while
                # processing another circle.

                first = member["firstName"]
                last = member["lastName"]
                if first and last:
                    name = " ".join([first, last])
                else:
                    name = first or last

                loc = member["location"]
                if not loc:
                    if err_msg := member["issues"]["title"]:
                        if member["issues"]["dialog"]:
                            err_msg += f": {member['issues']['dialog']}"
                    else:
                        err_msg = "Location information missing"
                    LOGGER.error("%s: %s", name, err_msg)
                    continue

                place = loc["name"] or None

                if place:
                    address: str | None = place
                else:
                    address1 = loc["address1"] or None
                    address2 = loc["address2"] or None
                    if address1 and address2:
                        address = ", ".join([address1, address2])
                    else:
                        address = address1 or address2

                speed = max(0, float(loc["speed"]) * SPEED_FACTOR_MPH)
                if self._hass.config.units.is_metric:
                    speed = convert(speed, LENGTH_MILES, LENGTH_KILOMETERS)

                data.members[member["id"]] = Life360Member(
                    address,
                    dt_util.utc_from_timestamp(int(loc["since"])),
                    bool(int(loc["charge"])),
                    int(float(loc["battery"])),
                    bool(int(loc["isDriving"])),
                    member["avatar"],
                    # Life360 reports accuracy in feet, but Device Tracker expects
                    # gps_accuracy in meters.
                    round(convert(float(loc["accuracy"]), LENGTH_FEET, LENGTH_METERS)),
                    dt_util.utc_from_timestamp(int(loc["timestamp"])),
                    float(loc["latitude"]),
                    float(loc["longitude"]),
                    name,
                    place,
                    round(speed, SPEED_DIGITS),
                    bool(int(loc["wifiState"])),
                )

        return data
