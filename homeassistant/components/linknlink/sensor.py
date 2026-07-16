"""Distance sensors for LinknLink eMotion Ultra target positions."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LinknLinkConfigEntry
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 0

POSITION_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="nearest_horizontal_distance",
        translation_key="nearest_horizontal_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="nearest_distance",
        translation_key="nearest_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ENVIRONMENT_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="illuminance",
        translation_key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="target_count",
        translation_key="target_count",
        icon="mdi:account-multiple",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="persons_in_fenced_zones",
        translation_key="persons_in_fenced_zones",
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ZONE_COUNT_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = tuple(
    SensorEntityDescription(
        key=f"zone_{zone}_target_counts",
        translation_key=f"zone_{zone}_target_count",
        icon="mdi:account-multiple",
        state_class=SensorStateClass.MEASUREMENT,
    )
    for zone in range(1, 5)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ultra position distance sensors."""
    async_add_entities(
        LinknLinkPositionSensor(entry.runtime_data, description)
        for description in POSITION_SENSOR_DESCRIPTIONS
    )
    async_add_entities(
        LinknLinkEnvironmentSensor(entry.runtime_data, description)
        for description in (
            *ENVIRONMENT_SENSOR_DESCRIPTIONS,
            *ZONE_COUNT_SENSOR_DESCRIPTIONS,
        )
    )


class LinknLinkPositionSensor(LinknLinkEntity, SensorEntity):
    """Representation of an Ultra nearest-target distance."""

    entity_description: SensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether the target position subscription is available."""
        state = self.coordinator.position_state
        return state is not None and state.subscribed

    @property
    @override
    def native_value(self) -> StateType:
        """Return the nearest target distance in meters."""
        state = self.coordinator.position_state
        if state is None or state.stale or state.latest_update is None:
            return None
        if self.entity_description.key == "nearest_horizontal_distance":
            return state.latest_update.nearest_horizontal_distance
        return state.latest_update.nearest_distance

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to high-frequency position updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_position_listener(
                self._async_handle_position_update
            )
        )

    @callback
    def _async_handle_position_update(self, _: object) -> None:
        """Write a new distance or expiry state."""
        self.async_write_ha_state()


class LinknLinkEnvironmentSensor(LinknLinkEntity, SensorEntity):
    """Representation of an Ultra environmental or count sensor."""

    entity_description: SensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether this state currently has a valid local source."""
        if self.entity_description.key == "target_count":
            position = self.coordinator.position_state
            if (
                position is not None
                and position.subscribed
                and not position.stale
                and position.latest_update is not None
            ):
                return True
        state = self.coordinator.environment_state
        if not self.coordinator.environment_available or state is None:
            return False
        if self.entity_description.key in {"temperature", "humidity"}:
            return self.entity_description.key in state.available_fields
        return True

    @property
    @override
    def native_value(self) -> StateType:
        """Return the latest locally reported value."""
        if self.entity_description.key == "target_count":
            position = self.coordinator.position_state
            if (
                position is not None
                and position.subscribed
                and not position.stale
                and position.latest_update is not None
            ):
                return position.latest_update.target_count
        state = self.coordinator.environment_state
        if state is None:
            return None
        return state.values.get(self.entity_description.key)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe target count to real-time position updates."""
        await super().async_added_to_hass()
        if self.entity_description.key == "target_count":
            self.async_on_remove(
                self.coordinator.async_add_position_listener(
                    self._async_handle_position_update
                )
            )

    @callback
    def _async_handle_position_update(self, _: object) -> None:
        """Write an updated target count."""
        self.async_write_ha_state()
