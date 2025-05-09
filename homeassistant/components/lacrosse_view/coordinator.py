"""DataUpdateCoordinator for LaCrosse View."""

from __future__ import annotations

from datetime import timedelta
import logging
from time import time

from lacrosse_view import HTTPError, LaCrosse, Location, LoginError, Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LaCrosseUpdateCoordinator(DataUpdateCoordinator[list[Sensor]]):
    """DataUpdateCoordinator for LaCrosse View."""

    username: str
    password: str
    name: str
    id: str
    hass: HomeAssistant
    devices: list[Sensor] | None = None
    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: LaCrosse,
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
            _LOGGER,
            config_entry=entry,
            name="LaCrosse View",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> list[Sensor]:
        """Get the data for LaCrosse View."""
        now = int(time())

        if self.last_update < now - 59 * 60:  # Get new token once in a hour
            _LOGGER.debug("Refreshing token")
            self.last_update = now
            try:
                await self.api.login(self.username, self.password)
            except LoginError as error:
                raise ConfigEntryAuthFailed from error

        if self.devices is None:
            _LOGGER.debug("Getting devices")
            try:
                self.devices = await self.api.get_devices(
                    location=Location(id=self.id, name=self.name),
                )
            except HTTPError as error:
                raise UpdateFailed from error

        try:
            # Fetch last hour of data
            for sensor in self.devices:
                data = await self.api.get_sensor_status(
                    sensor=sensor,
                    tz=self.hass.config.time_zone,
                )
                _LOGGER.debug("Got data: %s", data)

                if data_error := data.get("error"):
                    if data_error == "no_readings":
                        sensor.data = None
                        _LOGGER.debug("No readings for %s", sensor.name)
                        continue
                    _LOGGER.debug("Error: %s", data_error)
                    raise UpdateFailed(
                        translation_domain=DOMAIN, translation_key="update_error"
                    )

                sensor.data = data["data"]["current"]

        except HTTPError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_error"
            ) from error

        # Verify that we have permission to read the sensors
        for sensor in self.devices:
            if not sensor.permissions.get("read", False):
                raise ConfigEntryAuthFailed(
                    f"This account does not have permission to read {sensor.name}"
                )

        return self.devices
