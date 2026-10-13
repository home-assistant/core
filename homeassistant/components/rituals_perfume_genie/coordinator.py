"""The Rituals Perfume Genie data update coordinators."""

from dataclasses import dataclass, replace
from datetime import datetime
import logging
from typing import override

from ritualsgenie import (
    RitualsGenie,
    RitualsGenieAuthenticationError,
    RitualsGenieError,
    RitualsGenieHub,
    RitualsGenieRateLimitError,
    RitualsGenieSensors,
    Sensor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    FILL_UPDATE_INTERVAL,
    SENSORS_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# The fill level is fetched separately, and far less often.
HOURLY_SENSORS = (Sensor.BATTERY, Sensor.PERFUME, Sensor.WIFI)

type RitualsConfigEntry = ConfigEntry[RitualsRuntimeData]


@dataclass
class RitualsRuntimeData:
    """The coordinators of a Rituals account."""

    hubs: RitualsHubsCoordinator
    sensors: dict[str, RitualsSensorsCoordinator]


def _update_failed(err: RitualsGenieError) -> Exception:
    """Return the exception a coordinator raises for a library error."""
    if isinstance(err, RitualsGenieAuthenticationError):
        return ConfigEntryAuthFailed(err)

    if isinstance(err, RitualsGenieRateLimitError):
        return UpdateFailed(str(err), retry_after=err.retry_after)

    return UpdateFailed(str(err))


class RitualsHubsCoordinator(DataUpdateCoordinator[dict[str, RitualsGenieHub]]):
    """Fetch the state of all diffusers on the account, in one request."""

    config_entry: RitualsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RitualsConfigEntry,
        client: RitualsGenie,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-hubs",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, RitualsGenieHub]:
        """Fetch the diffusers from Rituals."""
        try:
            hubs = await self.client.hubs()
        except RitualsGenieError as err:
            raise _update_failed(err) from err

        return {hub.hublot: hub for hub in hubs}


class RitualsSensorsCoordinator(DataUpdateCoordinator[RitualsGenieSensors | None]):
    """Fetch the sensor readings of a single diffuser.

    Every sensor is a request of its own, so only the sensors of enabled
    entities are fetched: each entity listens with its sensor as context.
    The data is None until the first update succeeded: a failing sensor
    doesn't keep the integration from setting up.
    """

    config_entry: RitualsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RitualsConfigEntry,
        hubs: RitualsHubsCoordinator,
        hublot: str,
    ) -> None:
        """Initialize the coordinator."""
        self.hubs = hubs
        self.hublot = hublot
        self._fill_updated: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{hublot}-sensors",
            update_interval=SENSORS_UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> RitualsGenieSensors | None:
        """Fetch the sensor readings from Rituals."""
        if (hub := self.hubs.data.get(self.hublot)) is None:
            raise UpdateFailed(f"Diffuser {self.hublot} is no longer on the account")

        client = self.hubs.client
        previous = self.data

        wanted = set(self.async_contexts())
        fill_wanted = Sensor.FILL in wanted and Sensor.FILL in hub.supported_sensors
        hourly = wanted.intersection(HOURLY_SENSORS)

        # The perfume tells when the cartridge changed, and so the fill level.
        if fill_wanted:
            hourly.add(Sensor.PERFUME)

        try:
            sensors = await client.sensors(hub, only=hourly)

            fill = previous.fill if previous else None
            if fill_wanted and self._fill_due(sensors):
                fill = await client.sensor(hub.hash, Sensor.FILL)
                self._fill_updated = dt_util.utcnow()

        except RitualsGenieError as err:
            raise _update_failed(err) from err

        return replace(sensors, fill=fill)

    def _fill_due(self, sensors: RitualsGenieSensors) -> bool:
        """Return if the fill level needs to be fetched again."""
        if self._fill_updated is None or self.data is None:
            return True

        # Another cartridge (or none at all) means another fill level.
        previous_perfume = self.data.perfume.raw if self.data.perfume else None
        current_perfume = sensors.perfume.raw if sensors.perfume else None
        if current_perfume != previous_perfume:
            return True

        return dt_util.utcnow() - self._fill_updated >= FILL_UPDATE_INTERVAL
