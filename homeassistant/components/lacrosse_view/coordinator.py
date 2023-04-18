"""DataUpdateCoordinator for LaCrosse View."""
from __future__ import annotations

from datetime import timedelta
from time import time

from lacrosse_view import HTTPError, LaCrosse, Location, LoginError, Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER, SCAN_INTERVAL


class LaCrosseUpdateCoordinator(DataUpdateCoordinator[list[Sensor]]):
    """DataUpdateCoordinator for LaCrosse View."""

    username: str
    password: str
    name: str
    id: str
    hass: HomeAssistant

    def __init__(
        self,
        hass: HomeAssistant,
        api: LaCrosse,
        entry: ConfigEntry,
    ) -> None:
        """Initialize DataUpdateCoordinator for LaCrosse View."""
        self.api = api
        self.last_update = time()
        self.username = entry.data["username"]
        self.password = entry.data["password"]
        self.hass = hass
        self.name = entry.data["name"]
        self.id = entry.data["id"]
        super().__init__(
            hass,
            LOGGER,
            name="LaCrosse View",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> list[Sensor]:
        """Get the data for LaCrosse View."""
        now = int(time())

        if self.last_update < now - 59 * 60:  # Get new token once in a hour
            self.last_update = now
            try:
                await self.api.login(self.username, self.password)
            except LoginError as error:
                raise ConfigEntryAuthFailed from error

        try:
            # Fetch last hour of data
            sensors = await self.api.get_sensors(
                location=Location(id=self.id, name=self.name),
                tz=self.hass.config.time_zone,
                start=str(now - 3600),
                end=str(now),
            )
        except HTTPError as error:
            raise ConfigEntryNotReady from error

        # Verify that we have permission to read the sensors
        for sensor in sensors:
            if not sensor.permissions.get("read", False):
                raise ConfigEntryAuthFailed(
                    f"This account does not have permission to read {sensor.name}"
                )

        return sensors
