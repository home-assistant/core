"""Support for Daikin Onecta binary sensors."""

from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinOnectaConfigEntry
from .device import DaikinOnectaDevice
from .discovery import (
    get_scalar_characteristic,
    scalar_characteristics_for_platform,
    scalar_platform,
)
from .entity import DaikinManagementPointEntity
from .entity_descriptions import BINARY_SENSOR_DESCRIPTIONS

PARALLEL_UPDATES = 1

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin binary sensors."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    sensors: list[DaikinBinarySensor] = []
    for device in (coordinator.data or {}).values():
        for management_point in device.device.management_points:
            for value, _characteristic in scalar_characteristics_for_platform(
                management_point, Platform.BINARY_SENSOR
            ):
                sensors.append(
                    DaikinBinarySensor(
                        device,
                        coordinator,
                        management_point.embedded_id,
                        BINARY_SENSOR_DESCRIPTIONS[value],
                        value,
                    )
                )

    async_add_entities(sensors)


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
        self._attr_unique_id = f"{self._device.id}_{self._embedded_id}_{self._value}"
        self.entity_description = description
        self.update_state()

    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        self._attr_is_on = self.sensor_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    def sensor_value(self) -> bool | None:
        """Return the binary characteristic value."""
        point = self._device.management_point(self._embedded_id)
        characteristic = (
            get_scalar_characteristic(point, self._value) if point is not None else None
        )
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
        if not super().available:
            return False
        point = self._device.management_point(self._embedded_id)
        if point is None:
            return False
        characteristic = get_scalar_characteristic(point, self._value)
        return bool(
            characteristic is not None
            and scalar_platform(
                self._value, characteristic, point.management_point_type
            )
            is Platform.BINARY_SENSOR
        )
