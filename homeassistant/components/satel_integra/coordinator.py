"""Coordinator for Satel Integra."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from satel_integra import AlarmState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SatelClient
from .const import CONF_ENABLE_TEMPERATURE_SENSOR, CONF_ZONE_NUMBER, SUBENTRY_TYPE_ZONE

_LOGGER = logging.getLogger(__name__)

PARTITION_UPDATE_DEBOUNCE_DELAY = 0.15
TEMPERATURE_SENSOR_UPDATE_INTERVAL = timedelta(minutes=5)


@dataclass
class SatelIntegraData:
    """Data for the satel_integra integration."""

    client: SatelClient
    coordinator_zones: SatelIntegraZonesCoordinator
    coordinator_outputs: SatelIntegraOutputsCoordinator
    coordinator_partitions: SatelIntegraPartitionsCoordinator
    coordinator_temperatures: SatelIntegraTemperaturesCoordinator


type SatelConfigEntry = ConfigEntry[SatelIntegraData]


class SatelIntegraBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """DataUpdateCoordinator base class for Satel Integra."""

    config_entry: SatelConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SatelConfigEntry,
        client: SatelClient,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize the base coordinator."""
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.entry_id} {self.__class__.__name__}",
            update_interval=update_interval,
        )

    def setup(self) -> None:
        """Set up client callbacks for this coordinator."""
        self.client.controller.add_connection_status_callback(
            self._async_handle_connection_state_update
        )

    @callback
    def _async_handle_connection_state_update(self) -> None:
        """Notify listeners on connection state changes from the client."""
        self.async_update_listeners()


class SatelIntegraZonesCoordinator(SatelIntegraBaseCoordinator[dict[int, bool]]):
    """DataUpdateCoordinator to handle zone updates."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client)

        self.data = {}

    @callback
    def zones_update_callback(self, status: dict[int, int]) -> None:
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Zones callback, status: %s", status)

        update_data = {zone: value == 1 for zone, value in status.items()}

        self.async_set_updated_data(update_data)


class SatelIntegraOutputsCoordinator(SatelIntegraBaseCoordinator[dict[int, bool]]):
    """DataUpdateCoordinator to handle output updates."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client)

        self.data = {}

    @callback
    def outputs_update_callback(self, status: dict[int, int]) -> None:
        """Update output objects as per notification from the alarm."""
        _LOGGER.debug("Outputs callback, status: %s", status)

        update_data = {output: value == 1 for output, value in status.items()}

        self.async_set_updated_data(update_data)


class SatelIntegraPartitionsCoordinator(
    SatelIntegraBaseCoordinator[dict[AlarmState, list[int]]]
):
    """DataUpdateCoordinator to handle partition state updates."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client)

        self.data = {}

        self._debouncer = Debouncer(
            hass=self.hass,
            logger=_LOGGER,
            cooldown=PARTITION_UPDATE_DEBOUNCE_DELAY,
            immediate=False,
            function=callback(
                lambda: self.async_set_updated_data(
                    self.client.controller.partition_states
                )
            ),
        )

    @callback
    def partitions_update_callback(self) -> None:
        """Update partition objects as per notification from the alarm."""
        _LOGGER.debug("Sending request to update panel state")

        self._debouncer.async_schedule_call()


class SatelIntegraTemperaturesCoordinator(
    SatelIntegraBaseCoordinator[dict[int, float | None]]
):
    """DataUpdateCoordinator to poll zone temperatures."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            entry,
            client,
            update_interval=TEMPERATURE_SENSOR_UPDATE_INTERVAL,
        )

        self._zone_numbers = [
            subentry.data[CONF_ZONE_NUMBER]
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
            if subentry.data.get(CONF_ENABLE_TEMPERATURE_SENSOR, False)
        ]

    async def _async_update_data(self) -> dict[int, float | None]:
        """Fetch temperatures from the alarm."""
        if not self._zone_numbers:
            return {}

        try:
            return await self.client.controller.read_temperatures(self._zone_numbers)
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch temperatures: {err}") from err
