"""Device tracker platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tesla_fleet_api.const import Scope
from teslemetry_stream import TeslemetryStreamVehicle
from teslemetry_stream.const import TeslaLocation

from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import TeslemetryConfigEntry
from .entity import TeslemetryVehiclePollingEntity, TeslemetryVehicleStreamEntity
from .models import TeslemetryVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslemetryDeviceTrackerEntityDescription(TrackerEntityDescription):
    """Describe a Teslemetry device tracker entity."""

    value_listener: Callable[
        [TeslemetryStreamVehicle, Callable[[TeslaLocation | None], None]],
        Callable[[], None],
    ]
    name_listener: (
        Callable[
            [TeslemetryStreamVehicle, Callable[[str | None], None]], Callable[[], None]
        ]
        | None
    ) = None
    streaming_firmware: str
    polling_prefix: str | None = None


DESCRIPTIONS: tuple[TeslemetryDeviceTrackerEntityDescription, ...] = (
    TeslemetryDeviceTrackerEntityDescription(
        key="location",
        polling_prefix="drive_state",
        value_listener=lambda x, y: x.listen_Location(y),
        streaming_firmware="2024.26",
    ),
    TeslemetryDeviceTrackerEntityDescription(
        key="route",
        polling_prefix="drive_state_active_route",
        value_listener=lambda x, y: x.listen_DestinationLocation(y),
        name_listener=lambda x, y: x.listen_DestinationName(y),
        streaming_firmware="2024.26",
    ),
    TeslemetryDeviceTrackerEntityDescription(
        key="origin",
        value_listener=lambda x, y: x.listen_OriginLocation(y),
        streaming_firmware="2024.26",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry device tracker platform from a config entry."""

    entities: list[
        TeslemetryVehiclePollingDeviceTrackerEntity
        | TeslemetryStreamingDeviceTrackerEntity
    ] = []
    # Only add vehicle location entities if the user has granted vehicle location scope.
    if Scope.VEHICLE_LOCATION not in entry.runtime_data.scopes:
        return

    for vehicle in entry.runtime_data.vehicles:
        for description in DESCRIPTIONS:
            if vehicle.api.pre2021 or vehicle.firmware < description.streaming_firmware:
                if description.polling_prefix:
                    entities.append(
                        TeslemetryVehiclePollingDeviceTrackerEntity(
                            vehicle, description
                        )
                    )
            else:
                entities.append(
                    TeslemetryStreamingDeviceTrackerEntity(vehicle, description)
                )

    async_add_entities(entities)


class TeslemetryVehiclePollingDeviceTrackerEntity(
    TeslemetryVehiclePollingEntity, TrackerEntity
):
    """Base class for Teslemetry Tracker Entities."""

    entity_description: TeslemetryDeviceTrackerEntityDescription

    def __init__(
        self,
        vehicle: TeslemetryVehicleData,
        description: TeslemetryDeviceTrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
        self.entity_description = description
        super().__init__(vehicle, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_latitude = self.get(
            f"{self.entity_description.polling_prefix}_latitude"
        )
        self._attr_longitude = self.get(
            f"{self.entity_description.polling_prefix}_longitude"
        )
        self._attr_location_name = self.get(
            f"{self.entity_description.polling_prefix}_destination"
        )
        if self._attr_location_name == "Home":
            self._attr_location_name = STATE_HOME
        self._attr_available = (
            self._attr_latitude is not None and self._attr_longitude is not None
        )


class TeslemetryStreamingDeviceTrackerEntity(
    TeslemetryVehicleStreamEntity, TrackerEntity, RestoreEntity
):
    """Base class for Teslemetry Tracker Entities."""

    entity_description: TeslemetryDeviceTrackerEntityDescription

    def __init__(
        self,
        vehicle: TeslemetryVehicleData,
        description: TeslemetryDeviceTrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
        self.entity_description = description
        super().__init__(vehicle, description.key)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._attr_state = state.state
            self._attr_latitude = state.attributes.get("latitude")
            self._attr_longitude = state.attributes.get("longitude")
            self._attr_location_name = state.attributes.get("location_name")
        self.async_on_remove(
            self.entity_description.value_listener(
                self.vehicle.stream_vehicle, self._location_callback
            )
        )
        if self.entity_description.name_listener:
            self.async_on_remove(
                self.entity_description.name_listener(
                    self.vehicle.stream_vehicle, self._name_callback
                )
            )

    def _location_callback(self, location: TeslaLocation | None) -> None:
        """Update the value of the entity."""
        if location is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_latitude = location.latitude
            self._attr_longitude = location.longitude
        self.async_write_ha_state()

    def _name_callback(self, name: str | None) -> None:
        """Update the value of the entity."""
        self._attr_location_name = name
        if self._attr_location_name == "Home":
            self._attr_location_name = STATE_HOME
        self.async_write_ha_state()
