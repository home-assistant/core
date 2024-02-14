"""Data update coordinator for Traccar Server."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, TypedDict

from pytraccar import (
    ApiClient,
    DeviceModel,
    GeofenceModel,
    PositionModel,
    TraccarException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENTS, LOGGER
from .helpers import get_device, get_first_geofence


class TraccarServerCoordinatorDataDevice(TypedDict):
    """Traccar Server coordinator data."""

    device: DeviceModel
    geofence: GeofenceModel | None
    position: PositionModel
    attributes: dict[str, Any]


TraccarServerCoordinatorData = dict[str, TraccarServerCoordinatorDataDevice]


class TraccarServerCoordinator(DataUpdateCoordinator[TraccarServerCoordinatorData]):
    """Class to manage fetching Traccar Server data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: ApiClient,
        *,
        events: list[str],
        max_accuracy: float,
        skip_accuracy_filter_for: list[str],
        custom_attributes: list[str],
    ) -> None:
        """Initialize global Traccar Server data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client
        self.custom_attributes = custom_attributes
        self.events = events
        self.max_accuracy = max_accuracy
        self.skip_accuracy_filter_for = skip_accuracy_filter_for
        self._last_event_import: datetime | None = None

    async def _async_update_data(self) -> TraccarServerCoordinatorData:
        """Fetch data from Traccar Server."""
        LOGGER.debug("Updating device data")
        data: TraccarServerCoordinatorData = {}
        try:
            (
                devices,
                positions,
                geofences,
            ) = await asyncio.gather(
                self.client.get_devices(),
                self.client.get_positions(),
                self.client.get_geofences(),
            )
        except TraccarException as ex:
            raise UpdateFailed(f"Error while updating device data: {ex}") from ex

        if TYPE_CHECKING:
            assert isinstance(devices, list[DeviceModel])  # type: ignore[misc]
            assert isinstance(positions, list[PositionModel])  # type: ignore[misc]
            assert isinstance(geofences, list[GeofenceModel])  # type: ignore[misc]

        for position in positions:
            if (device := get_device(position["deviceId"], devices)) is None:
                continue

            attr = {}
            skip_accuracy_filter = False

            for custom_attr in self.custom_attributes:
                attr[custom_attr] = device["attributes"].get(
                    custom_attr,
                    position["attributes"].get(custom_attr, None),
                )
                if custom_attr in self.skip_accuracy_filter_for:
                    skip_accuracy_filter = True

            accuracy = position["accuracy"] or 0.0
            if (
                not skip_accuracy_filter
                and self.max_accuracy > 0
                and accuracy > self.max_accuracy
            ):
                LOGGER.debug(
                    "Excluded position by accuracy filter: %f (%s)",
                    accuracy,
                    device["id"],
                )
                continue

            data[device["uniqueId"]] = {
                "device": device,
                "geofence": get_first_geofence(
                    geofences,
                    position["geofenceIds"] or [],
                ),
                "position": position,
                "attributes": attr,
            }

        if self.events:
            self.hass.async_create_task(self.import_events(devices))

        return data

    async def import_events(self, devices: list[DeviceModel]) -> None:
        """Import events from Traccar."""
        start_time = dt_util.utcnow().replace(tzinfo=None)
        end_time = None

        if self._last_event_import is not None:
            end_time = start_time - (start_time - self._last_event_import)

        events = await self.client.get_reports_events(
            devices=[device["id"] for device in devices],
            start_time=start_time,
            end_time=end_time,
            event_types=self.events,
        )
        if not events:
            return

        self._last_event_import = start_time
        for event in events:
            device = get_device(event["deviceId"], devices)
            self.hass.bus.async_fire(
                # This goes against two of the HA core guidelines:
                # 1. Event names should be prefixed with the domain name of
                #    the integration
                # 2. This should be event entities
                #
                # However, to not break it for those who currently use
                # the "old" integration, this is kept as is.
                f"traccar_{EVENTS[event['type']]}",
                {
                    "device_traccar_id": event["deviceId"],
                    "device_name": device["name"] if device else None,
                    "type": event["type"],
                    "serverTime": event["eventTime"],
                    "attributes": event["attributes"],
                },
            )
