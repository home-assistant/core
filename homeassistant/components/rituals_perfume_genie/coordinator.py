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
    RitualsGenieHublot,
    RitualsGenieRateLimitError,
    RitualsGenieSensors,
    Sensor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
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
        return ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        )

    if isinstance(err, RitualsGenieRateLimitError):
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="rate_limited",
            retry_after=err.retry_after,
        )

    # The coordinator logs this message, so the error of the library is kept.
    return UpdateFailed(
        translation_domain=DOMAIN,
        translation_key="update_failed",
        translation_placeholders={"error": str(err)},
    )


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
        self.hardware: dict[str, RitualsGenieHublot] = {}
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
        finally:
            # A login can succeed while the request after it fails. Keep that
            # token too, or every setup retry would log in again.
            self._async_store_token()

        await self._async_update_hardware(hubs)

        return {hub.hublot: hub for hub in hubs}

    @callback
    def _async_store_token(self) -> None:
        """Store a new token, so a restart doesn't need another login.

        Rituals locks an account after about a dozen logins in an hour, which
        a few restarts in a row would otherwise get close to. The client logs
        in by itself; this update runs often enough to pick up any new token.
        """
        token = self.client.token
        if token is None or token == self.config_entry.data.get(CONF_TOKEN):
            return

        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, CONF_TOKEN: token}
        )

    async def _async_update_hardware(self, hubs: list[RitualsGenieHub]) -> None:
        """Fetch the hardware details of diffusers we don't know yet.

        Only this tells which model a diffuser is. That never changes, so it
        is fetched once per diffuser. Not worth failing the update over: the
        next update tries again.
        """
        device_registry = dr.async_get(self.hass)

        for hub in hubs:
            if hub.hublot in self.hardware:
                continue

            try:
                hardware = await self.client.hublot(hub.hublot)
            except RitualsGenieError as err:
                _LOGGER.debug("Could not fetch the model of %s: %s", hub.hublot, err)
                continue

            self.hardware[hub.hublot] = hardware

            # A diffuser that is already known gets its model right away.
            device = device_registry.async_get_device_by_identifier(
                (DOMAIN, hub.hublot), self.config_entry.entry_id
            )
            if device and hardware.device_version:
                device_registry.async_update_device(
                    device.id, model=hardware.device_version
                )


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
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="diffuser_not_found",
                translation_placeholders={"hublot": self.hublot},
            )

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
