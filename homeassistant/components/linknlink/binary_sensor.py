"""Occupancy sensors for LinknLink eMotion Ultra."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LinknLinkConfigEntry
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 0

OCCUPANCY_DESCRIPTION = BinarySensorEntityDescription(
    key="occupancy",
    translation_key="occupancy",
    device_class=BinarySensorDeviceClass.OCCUPANCY,
)

ZONE_OCCUPANCY_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = tuple(
    BinarySensorEntityDescription(
        key=f"zone_{zone}_presence",
        translation_key=f"zone_{zone}_occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    )
    for zone in range(1, 5)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ultra occupancy sensors."""
    async_add_entities(
        LinknLinkOccupancySensor(entry.runtime_data, description)
        for description in (OCCUPANCY_DESCRIPTION, *ZONE_OCCUPANCY_DESCRIPTIONS)
    )


class LinknLinkOccupancySensor(LinknLinkEntity, BinarySensorEntity):
    """Representation of an Ultra occupancy state."""

    entity_description: BinarySensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether a current occupancy source is available."""
        state = self.coordinator.environment_state
        if self.coordinator.environment_available and state is not None:
            return True
        if self.entity_description.key != "occupancy":
            return False
        position = self.coordinator.position_state
        return (
            position is not None
            and position.subscribed
            and not position.stale
            and position.latest_update is not None
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return occupancy, using live targets as an immediate positive signal."""
        if self.entity_description.key == "occupancy":
            position = self.coordinator.position_state
            if (
                position is not None
                and position.subscribed
                and not position.stale
                and position.latest_update is not None
                and position.latest_update.target_count > 0
            ):
                return True
        state = self.coordinator.environment_state
        if state is None:
            if self.entity_description.key != "occupancy":
                return None
            position = self.coordinator.position_state
            if position is None or position.latest_update is None:
                return None
            return position.latest_update.target_count > 0
        value = state.values.get(self.entity_description.key)
        return value if isinstance(value, bool) else None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe overall occupancy to real-time position updates."""
        await super().async_added_to_hass()
        if self.entity_description.key == "occupancy":
            self.async_on_remove(
                self.coordinator.async_add_position_listener(
                    self._async_handle_position_update
                )
            )

    @callback
    def _async_handle_position_update(self, _: object) -> None:
        """Write an updated overall occupancy state."""
        self.async_write_ha_state()
