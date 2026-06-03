"""DataUpdateCoordinator for LaCrosse View."""

from datetime import timedelta
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
        self.last_update = time()
        self.username = entry.data["username"]
        self.password = entry.data["password"]
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

        if now - self.last_update > 59 * 60:
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
                    location=Location(id=self.id, name=self.name)
                )
            except HTTPError as error:
                raise UpdateFailed from error

        for sensor in self.devices:
            try:
                sensor.data = await self.api.get_sensor_status_filtered(
                    sensor=sensor,
                    tz=self.hass.config.time_zone,
                    stale_threshold=STALE_DATA_THRESHOLD,
                    previous_data=sensor.data,
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

        for sensor in self.devices:
            if not sensor.permissions.get("read", False):
                raise ConfigEntryAuthFailed(
                    f"This account does not have permission to read {sensor.name}"
                )

        return self.devices
