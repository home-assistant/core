"""Support for getting collected information from Combined Energy."""
from __future__ import annotations

from collections.abc import Generator, Sequence
from typing import Any

from combined_energy import CombinedEnergy
from combined_energy.models import Device, DeviceReadings, Installation

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_API_CLIENT,
    DATA_INSTALLATION,
    DOMAIN,
    SENSOR_DESCRIPTION_CONNECTED,
    SENSOR_DESCRIPTIONS,
)
from .coordinator import (
    CombinedEnergyConnectivityDataService,
    CombinedEnergyReadingsDataService,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""

    api: CombinedEnergy = hass.data[DOMAIN][entry.entry_id][DATA_API_CLIENT]
    installation: Installation = hass.data[DOMAIN][entry.entry_id][DATA_INSTALLATION]

    # Initialise services
    await api.start_log_session()
    connection = CombinedEnergyConnectivityDataService(hass, api)
    readings = CombinedEnergyReadingsDataService(hass, api)
    for service in (connection, readings):
        service.async_setup()
        await service.coordinator.async_refresh()

    # Build entity list
    sensor_factory = CombinedEnergyReadingsSensorFactory(hass, installation, readings)
    entities: list[CombinedEnergyReadingsSensor | CombinedEnergyConnectedSensor] = list(
        sensor_factory.entities()
    )
    entities.insert(0, CombinedEnergyConnectedSensor(entry.title, connection))

    async_add_entities(entities)


class CombinedEnergyConnectedSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Combined Energy connection status sensor."""

    data_service: CombinedEnergyConnectivityDataService

    def __init__(
        self, platform_name: str, data_service: CombinedEnergyConnectivityDataService
    ) -> None:
        """Initialise Connected Sensor."""
        super().__init__(data_service.coordinator)

        self.data_service = data_service
        self.entity_description = SENSOR_DESCRIPTION_CONNECTED

        self._attr_name = f"{platform_name} {self.entity_description.name}"
        self._attr_unique_id = f"install_{self.data_service.api.installation_id}-{self.entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        if self.data_service.data is not None:
            return self.data_service.data.connected
        return None


class CombinedEnergyReadingsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Combined Energy API reading energy sensor."""

    data_service: CombinedEnergyReadingsDataService
    entity_description: SensorEntityDescription

    def __init__(
        self,
        device: Device,
        device_info: DeviceInfo,
        description: SensorEntityDescription,
        data_service: CombinedEnergyReadingsDataService,
    ) -> None:
        """Initialise Readings Sensor."""
        super().__init__(data_service.coordinator)

        self.device_id = device.device_id
        self.data_service = data_service
        self.entity_description = description

        self._attr_name = f"{device.display_name} {description.name}"
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"install_{self.data_service.api.installation_id}-"
            f"device_{device.device_id}-"
            f"{description.key}"
        )

    @property
    def device_readings(self) -> DeviceReadings | None:
        """Get readings for specific device."""
        if data := self.data_service.data:
            return data[self.device_id]
        return None

    @property
    def _raw_value(self):
        """Get raw reading value from device."""
        if device_readings := self.device_readings:
            return getattr(device_readings, self.entity_description.key)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return {}

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        value = self._raw_value
        if isinstance(value, Sequence):
            value = value[-1]
        return round(value, 2) if value is not None else None


class EnergySensor(CombinedEnergyReadingsSensor):
    """Sensor for energy readings."""

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor for a power value."""
        if (value := self._raw_value) is not None:
            return round(sum(value), 2)
        return None


class PowerSensor(CombinedEnergyReadingsSensor):
    """Sensor for power readings."""

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor for a power value."""
        if (value := self._raw_value) is not None:
            return round(value, 2)
        return None


class WaterVolumeSensor(CombinedEnergyReadingsSensor):
    """Sensor for water volume readings."""

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor for a power value."""
        if (value := self._raw_value) is not None:
            return int(round(value[-1], 0))
        return None


SENSOR_TYPE_MAP: dict[
    SensorDeviceClass | str | None, type[CombinedEnergyReadingsSensor]
] = {
    SensorDeviceClass.ENERGY: EnergySensor,
    SensorDeviceClass.POWER: PowerSensor,
    SensorDeviceClass.WATER: WaterVolumeSensor,
    None: CombinedEnergyReadingsSensor,
}


class CombinedEnergyReadingsSensorFactory:
    """
    Factory for generating devices/entities.

    Entities/Devices are described in the installation model.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        installation: Installation,
        readings: CombinedEnergyReadingsDataService,
    ) -> None:
        """Initialise readings sensor factory."""
        self.hass = hass
        self.installation = installation
        self.readings = readings

    def entities(self) -> Generator[CombinedEnergyReadingsSensor, None, None]:
        """Generate entities."""

        for device in self.installation.devices:
            if descriptions := SENSOR_DESCRIPTIONS.get(device.device_type):
                device_info = DeviceInfo(
                    identifiers={
                        (
                            DOMAIN,
                            f"install_{self.installation.installation_id}-device_{device.device_id}",
                        )
                    },
                    manufacturer=device.device_manufacturer,
                    model=device.device_model_name,
                    name=device.display_name,
                )

                for description in descriptions:
                    if sensor_type := SENSOR_TYPE_MAP.get(
                        description.device_class, CombinedEnergyReadingsSensor
                    ):
                        yield sensor_type(
                            device,
                            device_info,
                            description,
                            self.readings,
                        )
