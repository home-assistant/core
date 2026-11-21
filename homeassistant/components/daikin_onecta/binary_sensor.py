"""Support for Daikin Onecta binary sensors."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .discovery import scalar_characteristics_for_platform
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    management_point_unique_id,
    present_devices,
)
from .entity_metadata import (
    BINARY_SENSOR_TRANSLATION_KEYS,
    ENTITY_METADATA,
    entity_description_kwargs,
)

PARALLEL_UPDATES = 1

BINARY_SENSOR_DESCRIPTIONS = {
    metadata.key: BinarySensorEntityDescription(
        key=metadata.key,
        device_class=metadata.device_class
        if isinstance(metadata.device_class, BinarySensorDeviceClass)
        else None,
        **entity_description_kwargs(metadata),
    )
    for metadata in ENTITY_METADATA
    if metadata.translation_key in BINARY_SENSOR_TRANSLATION_KEYS
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin binary sensors."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: _create_binary_sensors(coordinator, is_known),
    )


def _create_binary_sensors(
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[DaikinBinarySensor]:
    """Create supported binary sensors from the current cloud model."""
    sensors: list[DaikinBinarySensor] = []
    for device in present_devices(coordinator):
        for management_point in device.device.management_points:
            for value, _characteristic in scalar_characteristics_for_platform(
                management_point,
                Platform.BINARY_SENSOR,
                gateway_online=getattr(device.device, "available", True),
            ):
                unique_id = management_point_unique_id(
                    device.id, management_point.embedded_id, value
                )
                if is_known(Platform.BINARY_SENSOR, unique_id):
                    continue
                sensors.append(
                    DaikinBinarySensor(
                        device,
                        coordinator,
                        management_point.embedded_id,
                        BINARY_SENSOR_DESCRIPTIONS[value],
                        value,
                    )
                )

    return sensors


class DaikinBinarySensor(DaikinManagementPointEntity, BinarySensorEntity):
    """Represent a boolean Daikin characteristic."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
        description: BinarySensorEntityDescription,
        value: str,
    ) -> None:
        """Initialize the binary sensor from a device characteristic."""
        super().__init__(device, coordinator, embedded_id)
        self._value = value
        self._attr_unique_id = management_point_unique_id(
            self._device_id, self._embedded_id, self._value
        )
        management_point = self._management_point
        if (
            self._value == "isInErrorState"
            and management_point is not None
            and management_point.management_point_type == "gateway"
        ):
            self._attr_translation_key = "gateway_isinerrorstate"
        self.entity_description = description
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        self._attr_is_on = self.sensor_value()

    def sensor_value(self) -> bool | None:
        """Return the binary characteristic value."""
        characteristic = self._characteristic(self._value)
        result = characteristic.value if characteristic is not None else None
        if isinstance(result, bool):
            return result
        if result == "on":
            return True
        if result == "off":
            return False
        return None

    @property
    @override
    def available(self) -> bool:
        """Return whether the source characteristic is still available."""
        return super().available and self._characteristic_exposed_on(
            self._value, Platform.BINARY_SENSOR
        )
