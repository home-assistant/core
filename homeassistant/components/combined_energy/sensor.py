"""Support for getting collected information from Combined Energy."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Generator, Sequence
from datetime import datetime

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
    DATA_LOG_SESSION,
    DOMAIN,
    SENSOR_DESCRIPTION_CONNECTED,
    SENSOR_DESCRIPTIONS,
)
from .coordinator import (
    CombinedEnergyConnectivityDataService,
    CombinedEnergyLogSessionService,
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
    connection = CombinedEnergyConnectivityDataService(hass, api)
    log_session = CombinedEnergyLogSessionService(hass, api)
    readings = CombinedEnergyReadingsDataService(hass, api)
    for service in (connection, log_session, readings):
        service.async_setup()
        await service.coordinator.async_refresh()

    # Store log session into Data
    hass.data[DOMAIN][entry.entry_id][DATA_LOG_SESSION] = log_session

    # Build entity list
    sensor_factory = CombinedEnergyReadingsSensorFactory(hass, installation, readings)
    entities: list[CombinedEnergyReadingsSensor | CombinedEnergyConnectedSensor] = list(
        sensor_factory.entities()
    )
    # Insert connected as the first sensor
    entities.insert(0, CombinedEnergyConnectedSensor(entry.title, connection))

    async_add_entities(entities)


class CombinedEnergyConnectedSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Combined Energy connection status sensor."""

    data_service: CombinedEnergyConnectivityDataService

    def __init__(
        self, entry_title: str, data_service: CombinedEnergyConnectivityDataService
    ) -> None:
        """Initialise Connected Sensor."""
        super().__init__(data_service.coordinator)

        self.data_service = data_service
        self.entity_description = SENSOR_DESCRIPTION_CONNECTED

        self._attr_name = f"{entry_title} {self.entity_description.name}"
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

    native_value_rounding: int = 2

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
            return data.get(self.device_id, None)
        return None

    @property
    def _raw_value(self):
        """Get raw reading value from device readings."""
        if device_readings := self.device_readings:
            return getattr(device_readings, self.entity_description.key)
        return None

    @property
    def available(self) -> bool:
        """Indicate if the entity is available."""
        return self._raw_value is not None

    @abstractmethod
    def _to_native_value(self, raw_value):
        """Convert non-none raw value into usable sensor value."""

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        if (raw_value := self._raw_value) is not None:
            return self._to_native_value(raw_value)
        return None


class GenericSensor(CombinedEnergyReadingsSensor):
    """Sensor that returns the last value of a sequence of readings."""

    def _to_native_value(self, raw_value):
        """Convert non-none raw value into usable sensor value."""
        if isinstance(raw_value, Sequence):
            raw_value = raw_value[-1]
        return round(raw_value, self.native_value_rounding)


class EnergySensor(CombinedEnergyReadingsSensor):
    """Sensor for energy readings."""

    @property
    def last_reset(self) -> datetime | None:
        """Last time the data was reset."""
        if device_readings := self.device_readings:
            return device_readings.range_start
        return None

    def _to_native_value(self, raw_value):
        """Convert non-none raw value into usable sensor value."""
        value = sum(raw_value)
        return round(value, self.native_value_rounding)


class PowerSensor(CombinedEnergyReadingsSensor):
    """Sensor for power readings."""

    def _to_native_value(self, raw_value):
        """Convert non-none raw value into usable sensor value."""
        return round(raw_value, self.native_value_rounding)


class PowerFactorSensor(CombinedEnergyReadingsSensor):
    """Sensor for power factor readings."""

    native_value_rounding = 1

    def _to_native_value(self, raw_value):
        """Convert non-none raw value into usable sensor value."""
        # The API expresses the power factor as a fraction convert to %
        return round(raw_value[-1] * 100, self.native_value_rounding)


class WaterVolumeSensor(CombinedEnergyReadingsSensor):
    """Sensor for water volume readings."""

    def _to_native_value(self, raw_value):
        """Convert non-none raw value into usable sensor value."""
        return int(round(raw_value[-1], 0))


# Map of common device classes to specific sensor types
SENSOR_TYPE_MAP: dict[
    SensorDeviceClass | str | None, type[CombinedEnergyReadingsSensor]
] = {
    SensorDeviceClass.ENERGY: EnergySensor,
    SensorDeviceClass.POWER: PowerSensor,
    SensorDeviceClass.WATER: WaterVolumeSensor,
    SensorDeviceClass.POWER_FACTOR: PowerFactorSensor,
    None: GenericSensor,
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

    def _generate_device_info(self, device: Device) -> DeviceInfo:
        """Generate device info from API device response."""
        return DeviceInfo(
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

    def entities(self) -> Generator[CombinedEnergyReadingsSensor, None, None]:
        """Generate entities."""

        for device in self.installation.devices:
            if descriptions := SENSOR_DESCRIPTIONS.get(device.device_type):
                device_info = self._generate_device_info(device)

                # Generate sensors from descriptions for the current device type
                for description in descriptions:
                    if sensor_type := SENSOR_TYPE_MAP.get(
                        description.device_class, GenericSensor
                    ):
                        yield sensor_type(
                            device,
                            device_info,
                            description,
                            self.readings,
                        )
