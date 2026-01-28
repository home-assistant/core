"""Coordinator for Satel Integra."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from satel_integra.satel_integra import AlarmState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import SatelClient
from .const import ZONES

_LOGGER = logging.getLogger(__name__)


@dataclass
class SatelIntegraData:
    """Data for the satel_integra integration."""

    client: SatelClient
    coordinator_zones: SatelIntegraZonesCoordinator
    coordinator_outputs: SatelIntegraOutputsCoordinator
    coordinator_partitions: SatelIntegraPartitionsCoordinator


type SatelConfigEntry = ConfigEntry[SatelIntegraData]


class SatelIntegraBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """DataUpdateCoordinator base class for Satel Integra."""

    config_entry: SatelConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the base coordinator."""
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.entry_id} {self.__class__.__name__}",
        )


class SatelIntegraZonesCoordinator(SatelIntegraBaseCoordinator[dict[int, bool]]):
    """DataUpdateCoordinatot to handle zone updates."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client)

        self.data = {}
        client.zones_update_callback = self.zones_update_callback

    @callback
    def zones_update_callback(self, status: dict[str, dict[int, int]]):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Zones callback, status: %s", status)

        update_data = {zone: value == 1 for zone, value in status[ZONES].items()}

        self.async_set_updated_data(update_data)


class SatelIntegraOutputsCoordinator(SatelIntegraBaseCoordinator[dict[int, bool]]):
    """DataUpdateCoordinator to handle output updates."""

    def __init__(
        self, hass: HomeAssistant, entry: SatelConfigEntry, client: SatelClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client)

        self.data = {}
        client.outputs_update_callback = self.outputs_update_callback

    @callback
    def outputs_update_callback(self, status: dict[str, dict[int, int]]):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Outputs callback, status: %s", status)

        update_data = {
            output: value == 1 for output, value in status["outputs"].items()
        }

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
        client.partitions_update_callback = self.partitions_update_callback

    @callback
    def partitions_update_callback(self):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Sending request to update panel state")

        self.async_set_updated_data(self.client.controller.partition_states)
