"""Device tracker platform for Teslemetry integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from teslemetry_stream.const import Signal
from teslemetry_stream import TeslemetryStreamVehicle

from homeassistant.components.device_tracker.config_entry import TrackerEntity, TrackerEntityDescription,
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeslemetryConfigEntry
from .entity import TeslemetryVehicleEntity, TeslemetryVehicleStreamEntity
from .models import TeslemetryVehicleData

PARALLEL_UPDATES = 0

@dataclass(frozen=True, kw_only=True)
class TeslemetryDeviceTrackerEntityDescription(TrackerEntityDescription):
    """Describe a Teslemetry device tracker entity."""

    streaming_key: Signal
    streaming_listener: Callable[[TeslemetryStreamVehicle],Callable[[Callable[[dict | None], None]],Callable[[],None]]
    streaming_name_key: Signal | None = None
    streaming_firmware: str
    polling_prefix: str | None = None

DESCRIPTIONS: tuple[TeslemetryDeviceTrackerEntityDescription,...] = (
    TeslemetryDeviceTrackerEntityDescription(
        key="location",
        polling_prefix="drive_state",
        streaming_key=Signal.LOCATION,
        streaming_listener=lambda x: x.
        streaming_firmware="2024.26"
    ),
    TeslemetryDeviceTrackerEntityDescription(
        key="route",
        polling_prefix="drive_state_active_route",
        streaming_key=Signal.DESTINATION_LOCATION,
        streaming_name_key=Signal.DESTINATION_NAME,
        streaming_firmware="2024.26"
    ),
    TeslemetryDeviceTrackerEntityDescription(
        key="origin",
        streaming_key=Signal.ORIGIN_LOCATION,
        streaming_firmware="2024.26",
        entity_registry_enabled_default=False,
    )
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Teslemetry device tracker platform from a config entry."""

    entities = []
    for vehicle in entry.runtime_data.vehicles:
        for description in DESCRIPTIONS:
            if vehicle.api.pre2021 or vehicle.firmware < description.streaming_firmware:
                if description.polling_prefix:
                    entities.append(
                        TeslemetryPollingDeviceTrackerEntity(vehicle, description)
                    )
            else:
                entities.append(
                    TeslemetryStreamingDeviceTrackerEntity(vehicle, description)
                )

    async_add_entities(entities)


class TeslemetryPollingDeviceTrackerEntity(TeslemetryVehicleEntity, TrackerEntity):
    """Base class for Teslemetry Tracker Entities."""

    entity_description = TeslemetryDeviceTrackerEntityDescription
    _attr_entity_category = None

    def __init__(
        self,
        vehicle: TeslemetryVehicleData,
        description: TeslemetryDeviceTrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(vehicle, description.key)
        self.entity_description = description

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_latitude = self.get(f"{self.entity_description.polling_prefix}_latitude")
        self._attr_longitude = self.get(f"{self.entity_description.polling_prefix}_longitude")
        self._attr_location_name = self.get(f"{self.entity_description.polling_prefix}_destination")
        if self._attr_location_name == "Home":
            self._attr_location_name = STATE_HOME
        self._attr_available = not (
            self.exactly(None, f"{self.entity_description.polling_prefix}_longitude")
            or self.exactly(None, f"{self.entity_description.polling_prefix}_latitude")
        )

class TeslemetryStreamingDeviceTrackerEntity(TeslemetryVehicleComplexStreamEntity, TrackerEntity, RestoreEntity):
    """Base class for Teslemetry Tracker Entities."""

    entity_description: TeslemetryDeviceTrackerEntityDescription
    _attr_entity_category = None

    def __init__(
        self,
        vehicle: TeslemetryVehicleData,
        description: TeslemetryDeviceTrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
        keys = [description.streaming_key]
        if description.streaming_name_key:
            keys.append(description.streaming_name_key)
        super().__init__(vehicle, description.key, keys)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._attr_state = state.state
            self._attr_latitude = state.attributes.get('latitude')
            self._attr_longitude = state.attributes.get('longitude')
            self._attr_location_name = state.attributes.get('location_name')

    def _async_data_from_stream(self, data) -> None:
        """Update the value of the entity."""
        if self.entity_description.streaming_key in data:
            value = data[self.entity_description.streaming_key]
            self._attr_available = isinstance(value, dict)
            if self._attr_available:
                self._attr_latitude = value.get("latitude")
                self._attr_longitude = value.get("longitude")
        if self.entity_description.streaming_name_key and self.entity_description.streaming_name_key in data:
            self._attr_location_name = data[self.entity_description.streaming_name_key]
            if self._attr_location_name == "Home":
                self._attr_location_name = STATE_HOME
