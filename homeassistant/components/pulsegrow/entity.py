"""Base entity for PulseGrow integration."""

from __future__ import annotations

from aiopulsegrow import DeviceType, Hub, Sensor, SensorType

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PulseGrowDataUpdateCoordinator


class PulseGrowEntity(CoordinatorEntity[PulseGrowDataUpdateCoordinator]):
    """Base class for PulseGrow entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PulseGrowDataUpdateCoordinator,
        entity_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entity_id = entity_id


class PulseGrowDeviceEntity(PulseGrowEntity):
    """Base class for PulseGrow device entities."""

    def __init__(
        self,
        coordinator: PulseGrowDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the device entity."""
        super().__init__(coordinator, device_id)
        device = coordinator.data.devices[device_id]

        # Determine device model from device_type
        model: str | None = None
        try:
            device_type = DeviceType(device.device_type)
            model = device_type.name.replace("_", " ").title()
        except ValueError:
            pass

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=model,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._entity_id in self.coordinator.data.devices


class PulseGrowHubEntity(PulseGrowEntity):
    """Base class for PulseGrow hub entities."""

    # Device info is set by __init__.py when registering hub devices

    @property
    def hub(self) -> Hub:
        """Return the hub data."""
        return self.coordinator.data.hubs[self._entity_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._entity_id in self.coordinator.data.hubs


class PulseGrowSensorEntity(PulseGrowEntity):
    """Base class for PulseGrow hub-connected sensor entities."""

    def __init__(
        self,
        coordinator: PulseGrowDataUpdateCoordinator,
        sensor_id: str,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, sensor_id)
        sensor = coordinator.data.sensors[sensor_id]

        # Determine sensor model from sensor_type
        model: str | None = None
        try:
            sensor_type_enum = SensorType(sensor.sensor_type)
            model = sensor_type_enum.name.replace("_", " ").upper()
        except ValueError:
            model = str(sensor.sensor_type)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor_id)},
            name=sensor.name,
            manufacturer=MANUFACTURER,
            model=model,
        )

        # Link to parent hub if available
        if sensor.hub_id is not None:
            self._attr_device_info["via_device"] = (DOMAIN, str(sensor.hub_id))

    @property
    def sensor(self) -> Sensor:
        """Return the sensor data."""
        return self.coordinator.data.sensors[self._entity_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._entity_id in self.coordinator.data.sensors
