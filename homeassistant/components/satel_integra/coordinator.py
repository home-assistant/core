"""Coordinator for Satel Integra."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from satel_integra import (
    AlarmState,
    SatelPanelInfo,
    SatelRtcAndStatus,
    SatelSystemTroubles,
)

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
    panel_info: SatelPanelInfo | None
    coordinator_zones: SatelIntegraZonesCoordinator
    coordinator_outputs: SatelIntegraOutputsCoordinator
    coordinator_partitions: SatelIntegraPartitionsCoordinator
    coordinator_system_status: SatelIntegraSystemStatusCoordinator
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
        self.config_entry.async_on_unload(
            self.client.controller.add_connection_status_callback(
                self._async_handle_connection_state_update
            )
        )

    @callback
    def _async_handle_connection_state_update(self) -> None:
        """Notify listeners on connection state changes from the client."""
        self.async_update_listeners()


class SatelIntegraZonesCoordinator(SatelIntegraBaseCoordinator[dict[int, bool | None]]):
    """DataUpdateCoordinator to handle zone updates."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client)

        self.data = {}

    @override
    def setup(self) -> None:
        """Set up client callbacks for this coordinator."""
        super().setup()
        self.config_entry.async_on_unload(
            self.client.controller.add_zone_changed_callback(self.zones_update_callback)
        )

    @callback
    def zones_update_callback(self) -> None:
        """Update zone objects as per notification from the alarm."""
        zone_states = self.client.controller.state.zones
        update_data = {
            zone: zone_state.violated for zone, zone_state in zone_states.items()
        }
        _LOGGER.debug("Zones callback, status: %s", update_data)

        self.async_set_updated_data(update_data)


class SatelIntegraOutputsCoordinator(
    SatelIntegraBaseCoordinator[dict[int, bool | None]]
):
    """DataUpdateCoordinator to handle output updates."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client)

        self.data = {}

    @override
    def setup(self) -> None:
        """Set up client callbacks for this coordinator."""
        super().setup()
        self.config_entry.async_on_unload(
            self.client.controller.add_output_changed_callback(
                self.outputs_update_callback
            )
        )

    @callback
    def outputs_update_callback(self) -> None:
        """Update output objects as per notification from the alarm."""
        output_states = self.client.controller.state.outputs
        update_data = {
            output: output_state.active
            for output, output_state in output_states.items()
        }
        _LOGGER.debug("Outputs callback, status: %s", update_data)

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
                    self.client.controller.state.partition_states
                )
            ),
        )

    @override
    def setup(self) -> None:
        """Set up client callbacks for this coordinator."""
        super().setup()
        self.config_entry.async_on_unload(
            self.client.controller.add_alarm_status_callback(
                self.partitions_update_callback
            )
        )

    @callback
    def partitions_update_callback(self) -> None:
        """Update partition objects as per notification from the alarm."""
        _LOGGER.debug("Sending request to update panel state")

        self._debouncer.async_schedule_call()


@dataclass(frozen=True)
class SatelIntegraSystemStatusData:
    """System status and trouble data reported by the panel."""

    status: SatelRtcAndStatus | None
    troubles: SatelSystemTroubles | None


class SatelIntegraSystemStatusCoordinator(
    SatelIntegraBaseCoordinator[SatelIntegraSystemStatusData]
):
    """DataUpdateCoordinator to handle system status updates."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client)

        self.data = self._get_data()

    @override
    def setup(self) -> None:
        """Set up client callbacks for this coordinator."""
        super().setup()
        self.config_entry.async_on_unload(
            self.client.controller.add_system_status_callback(
                self.system_status_update_callback
            )
        )

    @callback
    def system_status_update_callback(self) -> None:
        """Update the system status as per notification from the alarm."""
        self.async_set_updated_data(self._get_data())

    def _get_data(self) -> SatelIntegraSystemStatusData:
        """Return an immutable snapshot of the current system data."""
        state = self.client.controller.state
        return SatelIntegraSystemStatusData(
            status=state.system_status,
            troubles=state.system_troubles,
        )


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

    @override
    async def _async_update_data(self) -> dict[int, float | None]:
        """Fetch temperatures from the alarm."""
        if not self._zone_numbers:
            return {}

        try:
            return await self.client.controller.read_temperatures(self._zone_numbers)
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch temperatures: {err}") from err
