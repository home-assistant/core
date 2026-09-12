"""Sensor entities for the CoolBot Pro integration.

This integration is read-only. Set point is exposed as a sensor rather than as a
number or climate entity, so nothing here can change how the cooler runs.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pycoolbot import CoolbotDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import (
    CoolbotConfigEntry,
    CoolbotCoordinator,
    device_is_fresh,
    device_model,
)

# Everything is served from the coordinator's already-received state, so there is
# no I/O to throttle.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CoolbotSensorDescription(SensorEntityDescription):
    """Describes one CoolBot sensor."""

    value_fn: Callable[[CoolbotDevice], float | str | None]


# Temperatures are ALWAYS Fahrenheit on the wire. The app's F/C toggle is a local
# display preference and never changes what is sent, so Fahrenheit is declared as
# the native unit and Home Assistant converts for the user's chosen system.
SENSORS: tuple[CoolbotSensorDescription, ...] = (
    CoolbotSensorDescription(
        key="room_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.room_temp_f,
    ),
    CoolbotSensorDescription(
        key="fin_temperature",
        translation_key="fin_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.fins_temp_f,
    ),
    CoolbotSensorDescription(
        key="set_point",
        translation_key="set_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        suggested_display_precision=0,
        value_fn=lambda device: device.set_point_f,
    ),
    CoolbotSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.wifi_dbm,
    ),
    CoolbotSensorDescription(
        key="hardware_status",
        translation_key="hardware_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.hardware_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoolbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one set of sensors per real CoolBot on the account."""
    coordinator = entry.runtime_data
    async_add_entities(
        CoolbotSensor(coordinator, device, description)
        for device in coordinator.data.values()
        # Empty device slots are skipped entirely. The cloud serves stale pin
        # values for unused slots, so creating entities for them would publish
        # a believable temperature for hardware that does not exist.
        if device.is_provisioned
        for description in SENSORS
    )


class CoolbotSensor(CoordinatorEntity[CoolbotCoordinator], SensorEntity):
    """One reading from one CoolBot."""

    _attr_has_entity_name = True

    entity_description: CoolbotSensorDescription

    def __init__(
        self,
        coordinator: CoolbotCoordinator,
        device: CoolbotDevice,
        description: CoolbotSensorDescription,
    ) -> None:
        """Initialize the sensor from a device snapshot."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device.unique_id
        self._attr_unique_id = f"{device.unique_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            manufacturer=MANUFACTURER,
            name=device.name,
            model=device_model(device),
            sw_version=device.jumper_firmware,
            hw_version=device.jumper_hardware,
        )
        if device.mac_address:
            # Lets Home Assistant tie this to the same box seen by router or DHCP
            # integrations.
            self._attr_device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, device.mac_address)
            }

    @property
    def _device(self) -> CoolbotDevice:
        return self.coordinator.data[self._device_id]

    @property
    @override
    def available(self) -> bool:
        """Whether the reading can be trusted right now."""
        return (
            super().available
            and self._device_id in self.coordinator.data
            and device_is_fresh(self._device)
        )

    @property
    @override
    def native_value(self) -> float | str | None:
        """Return the current reading."""
        return self.entity_description.value_fn(self._device)
