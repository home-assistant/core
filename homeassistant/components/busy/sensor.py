"""Battery and Wi-Fi sensors for BUSY Bar."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BusyConfigEntry, BusyCoordinator
from .entity import BusyEntity

PARALLEL_UPDATES = 0
SENSORS = (
    SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key="wifi_ssid", translation_key="wifi_ssid"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the three readings from the shared coordinator.

    Create one entity for each sensor description using the shared state.
    """
    async_add_entities(
        BusySensor(entry.runtime_data, description) for description in SENSORS
    )


class BusySensor(BusyEntity, SensorEntity):
    """One value from the bar's last successful poll."""

    def __init__(
        self, coordinator: BusyCoordinator, description: SensorEntityDescription
    ) -> None:
        """Apply the reading's description to its stable identity.

        Bind the shared coordinator and the state required by this instance.
        """
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> int | str | None:
        """Return the selected reading, preserving missing values.

        Select one domain value by the entity description key.
        """
        data = self.coordinator.data
        return {
            "battery": data.battery,
            "wifi_signal": data.wifi_signal,
            "wifi_ssid": data.wifi_ssid,
        }[self.entity_description.key]
