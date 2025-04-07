"""Data update coordinator for Traccar Server."""

from __future__ import annotations

import asyncio
from datetime import datetime
from logging import DEBUG as LOG_LEVEL_DEBUG
from typing import TYPE_CHECKING, Any, TypedDict

from pytraccar import (
    ApiClient,
    DeviceModel,
    GeofenceModel,
    PositionModel,
    SubscriptionData,
    TraccarException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CUSTOM_ATTRIBUTES,
    CONF_EVENTS,
    CONF_MAX_ACCURACY,
    CONF_SKIP_ACCURACY_FILTER_FOR,
    DOMAIN,
    EVENTS,
    LOGGER,
)
from .helpers import get_device, get_first_geofence


class TraccarServerCoordinatorDataDevice(TypedDict):
    """Traccar Server coordinator data."""

    device: DeviceModel
    geofence: GeofenceModel | None
    position: PositionModel
    attributes: dict[str, Any]


type TraccarServerCoordinatorData = dict[int, TraccarServerCoordinatorDataDevice]


class TraccarServerCoordinator(DataUpdateCoordinator[TraccarServerCoordinatorData]):
    """Class to manage fetching Traccar Server data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: ApiClient,
    ) -> None:
        """Initialize global Traccar Server data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.client = client
        self.custom_attributes = config_entry.options.get(CONF_CUSTOM_ATTRIBUTES, [])
        self.events = config_entry.options.get(CONF_EVENTS, [])
        self.max_accuracy = config_entry.options.get(CONF_MAX_ACCURACY, 0.0)
        self.skip_accuracy_filter_for = config_entry.options.get(
            CONF_SKIP_ACCURACY_FILTER_FOR, []
        )
        self._geofences: list[GeofenceModel] = []
        self._last_event_import: datetime | None = None
        self._should_log_subscription_error: bool = True

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

        self._geofences = geofences

        if self.logger.isEnabledFor(LOG_LEVEL_DEBUG):
            self.logger.debug("Received devices: %s", devices)
            self.logger.debug("Received positions: %s", positions)

        for position in positions:
            device_id = position["deviceId"]
            if (device := get_device(device_id, devices)) is None:
                self.logger.debug(
                    "Device %s not found for position: %s",
                    device_id,
                    position["id"],
                )
                continue

            if (
                attr
                := self._return_custom_attributes_if_not_filtered_by_accuracy_configuration(
                    device, position
                )
            ) is None:
                self.logger.debug(
                    "Skipping position update %s for %s due to accuracy filter",
                    position["id"],
                    device_id,
                )
                continue

            data[device_id] = {
                "device": device,
                "geofence": get_first_geofence(
                    geofences,
                    position["geofenceIds"] or [],
                ),
                "position": position,
                "attributes": attr,
            }

        return data

    async def handle_subscription_data(self, data: SubscriptionData) -> None:
        """Handle subscription data."""
        self.logger.debug("Received subscription data: %s", data)
        self._should_log_subscription_error = True
        update_devices = set()
        for device in data.get("devices") or []:
            if (device_id := device["id"]) not in self.data:
                self.logger.debug("Device %s not found in data", device_id)
                continue

            if (
                attr
                := self._return_custom_attributes_if_not_filtered_by_accuracy_configuration(
                    device, self.data[device_id]["position"]
                )
            ) is None:
                continue

            self.data[device_id]["device"] = device
            self.data[device_id]["attributes"] = attr
            update_devices.add(device_id)

        for position in data.get("positions") or []:
            if (device_id := position["deviceId"]) not in self.data:
                self.logger.debug(
                    "Device %s for position %s not found in data",
                    device_id,
                    position["id"],
                )
                continue

            if (
                attr
                := self._return_custom_attributes_if_not_filtered_by_accuracy_configuration(
                    self.data[device_id]["device"], position
                )
            ) is None:
                self.logger.debug(
                    "Skipping position update %s for %s due to accuracy filter",
                    position["id"],
                    device_id,
                )
                continue

            self.data[device_id]["position"] = position
            self.data[device_id]["attributes"] = attr
            self.data[device_id]["geofence"] = get_first_geofence(
                self._geofences,
                position["geofenceIds"] or [],
            )
            update_devices.add(device_id)

        for device_id in update_devices:
            async_dispatcher_send(self.hass, f"{DOMAIN}_{device_id}")

    async def import_events(self, _: datetime) -> None:
        """Import events from Traccar."""
        start_time = dt_util.utcnow().replace(tzinfo=None)
        end_time = None

        if self._last_event_import is not None:
            end_time = start_time - (start_time - self._last_event_import)

        events = await self.client.get_reports_events(
            devices=list(self.data),
            start_time=start_time,
            end_time=end_time,
            event_types=self.events,
        )
        if not events:
            return

        self._last_event_import = start_time
        for event in events:
            device = self.data[event["deviceId"]]["device"]
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

    async def subscribe(self) -> None:
        """Subscribe to events."""
        try:
            await self.client.subscribe(self.handle_subscription_data)
        except TraccarException as ex:
            if self._should_log_subscription_error:
                self._should_log_subscription_error = False
                LOGGER.error("Error while subscribing to Traccar: %s", ex)
            # Retry after 10 seconds
            await asyncio.sleep(10)
            await self.subscribe()

    def _return_custom_attributes_if_not_filtered_by_accuracy_configuration(
        self,
        device: DeviceModel,
        position: PositionModel,
    ) -> dict[str, Any] | None:
        """Return a dictionary of custom attributes if not filtered by accuracy configuration."""
        attr = {}
        skip_accuracy_filter = False

        for custom_attr in self.custom_attributes:
            if custom_attr in self.skip_accuracy_filter_for:
                skip_accuracy_filter = True
            attr[custom_attr] = device["attributes"].get(
                custom_attr,
                position["attributes"].get(custom_attr, None),
            )

        accuracy = position["accuracy"] or 0.0
        if (
            not skip_accuracy_filter
            and self.max_accuracy > 0
            and accuracy > self.max_accuracy
        ):
            return None
        return attr
