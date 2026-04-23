"""DataUpdateCoordinator for LaCrosse View."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from time import time

from lacrosse_view import HTTPError, LaCrosse, Location, LoginError, Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL, STALE_DATA_THRESHOLD

_LOGGER = logging.getLogger(__name__)

type LaCrosseConfigEntry = ConfigEntry[LaCrosseUpdateCoordinator]


class LaCrosseUpdateCoordinator(DataUpdateCoordinator[list[Sensor]]):
    """DataUpdateCoordinator for LaCrosse View."""

    username: str
    password: str
    name: str
    id: str
    hass: HomeAssistant
    devices: list[Sensor] | None = None
    config_entry: LaCrosseConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LaCrosseConfigEntry,
        api: LaCrosse,
    ) -> None:
        """Initialize DataUpdateCoordinator for LaCrosse View."""
        self.api = api
        self.hass = hass

        self.username: str = entry.data["username"]
        self.password: str = entry.data["password"]
        self.name: str = entry.data["name"]
        self.id: str = entry.data["id"]

        self.last_login: float = time()
        self.devices: list[Sensor] | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="LaCrosse View",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> list[Sensor]:
        """Get the data for LaCrosse View."""
        now = int(time())

        # Refresh auth token once per hour
        if now - self.last_login > 59 * 60:
            _LOGGER.debug("Refreshing LaCrosse View token")
            self.last_login = now
            try:
                await self.api.login(self.username, self.password)
            except LoginError as error:
                raise ConfigEntryAuthFailed from error

        # Fetch devices once
        if self.devices is None:
            _LOGGER.debug("Getting devices")
            try:
                self.devices = await self.api.get_devices(
                    location=Location(id=self.id, name=self.name)
                )
            except HTTPError as error:
                raise UpdateFailed from error

        utc_now = datetime.now(tz=UTC)

        # Fetch last hour of data
        for sensor in self.devices:
            try:
                response = await self.api.get_sensor_status(
                    sensor=sensor,
                    tz=self.hass.config.time_zone,
                )
            except HTTPError as error:
                error_data = error.args[1] if len(error.args) > 1 else None

                if (
                    isinstance(error_data, dict)
                    and error_data.get("error") == "no_readings"
                ):
                    _LOGGER.debug("No readings for %s", sensor.name)
                    sensor.data = None
                    continue

                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_error",
                ) from error

            if response.get("error") == "no_readings":
                _LOGGER.debug("No readings for %s", sensor.name)
                sensor.data = None
                continue

            current_data = response.get("data", {}).get("current")
            if not current_data:
                _LOGGER.debug(
                    "No current data payload for %s, retaining old value", sensor.name
                )
                continue

            previous_data = sensor.data or {}
            filtered_data: dict[str, dict] = {}

            for field, field_data in current_data.items():
                spot = field_data.get("spot") if field_data else None
                if not spot:
                    continue

                timestamp = spot.get("time")
                # Only check for stale data if timestamp exists; data without timestamp is fresh
                if timestamp is not None:
                    try:
                        spot_time = datetime.fromtimestamp(timestamp, tz=UTC)
                    except TypeError, ValueError, OSError:
                        continue

                    age = utc_now - spot_time
                    if age > STALE_DATA_THRESHOLD:
                        _LOGGER.debug(
                            "Stale spot reading ignored: %s / %s (%.1f hours old), retaining old value",
                            sensor.name,
                            field,
                            age.total_seconds() / 3600,
                        )
                        if field in previous_data:
                            filtered_data[field] = previous_data[field]
                        continue

                filtered_data[field] = field_data

            sensor.data = filtered_data

        # Ensure read permission exists
        for sensor in self.devices:
            if not sensor.permissions.get("read", False):
                raise ConfigEntryAuthFailed(
                    f"This account does not have permission to read {sensor.name}"
                )

        return self.devices
