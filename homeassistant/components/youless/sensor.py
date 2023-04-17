"""The sensor entity for the Youless integration."""
from __future__ import annotations

from youless_api import YoulessAPI
from youless_api.youless_sensor import YoulessSensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize the integration."""
    coordinator: DataUpdateCoordinator[YoulessAPI] = hass.data[DOMAIN][entry.entry_id]
    device = entry.data[CONF_DEVICE]
    if (device := entry.data[CONF_DEVICE]) is None:
        device = entry.entry_id

    async_add_entities(
        [
            GasSensor(coordinator, device),
            EnergyMeterSensor(
                coordinator, device, "low", SensorStateClass.TOTAL_INCREASING
            ),
            EnergyMeterSensor(
                coordinator, device, "high", SensorStateClass.TOTAL_INCREASING
            ),
            EnergyMeterSensor(coordinator, device, "total", SensorStateClass.TOTAL),
            CurrentPowerSensor(coordinator, device),
            DeliveryMeterSensor(coordinator, device, "low"),
            DeliveryMeterSensor(coordinator, device, "high"),
            ExtraMeterSensor(coordinator, device, "total"),
            ExtraMeterPowerSensor(coordinator, device, "usage"),
            PhasePowerSensor(coordinator, device, 1),
            PhaseVoltageSensor(coordinator, device, 1),
            PhaseCurrentSensor(coordinator, device, 1),
            PhasePowerSensor(coordinator, device, 2),
            PhaseVoltageSensor(coordinator, device, 2),
            PhaseCurrentSensor(coordinator, device, 2),
            PhasePowerSensor(coordinator, device, 3),
            PhaseVoltageSensor(coordinator, device, 3),
            PhaseCurrentSensor(coordinator, device, 3),
        ]
    )


class YoulessBaseSensor(
    CoordinatorEntity[DataUpdateCoordinator[YoulessAPI]], SensorEntity
):
    """The base sensor for Youless."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[YoulessAPI],
        device: str,
        device_group: str,
        friendly_name: str,
        sensor_id: str,
    ) -> None:
        """Create the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{device}_{sensor_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device}_{device_group}")},
            manufacturer="YouLess",
            model=self.coordinator.data.model,
            name=friendly_name,
        )

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Property to get the underlying sensor object."""
        return None

    @property
    def native_value(self) -> StateType:
        """Determine the state value, only if a sensor is initialized."""
        if self.get_sensor is None:
            return None

        return self.get_sensor.value

    @property
    def available(self) -> bool:
        """Return a flag to indicate the sensor not being available."""
        return super().available and self.get_sensor is not None


class GasSensor(YoulessBaseSensor):
    """The Youless gas sensor."""

    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_device_class = SensorDeviceClass.GAS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: DataUpdateCoordinator[YoulessAPI], device: str
    ) -> None:
        """Instantiate a gas sensor."""
        super().__init__(coordinator, device, "gas", "Gas meter", "gas")
        self._attr_name = "Gas usage"
        self._attr_icon = "mdi:fire"

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor for providing the value."""
        return self.coordinator.data.gas_meter


class CurrentPowerSensor(YoulessBaseSensor):
    """The current power usage sensor."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: DataUpdateCoordinator[YoulessAPI], device: str
    ) -> None:
        """Instantiate the usage meter."""
        super().__init__(coordinator, device, "power", "Power usage", "usage")
        self._device = device
        self._attr_name = "Power Usage"

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor for providing the value."""
        return self.coordinator.data.current_power_usage


class DeliveryMeterSensor(YoulessBaseSensor):
    """The Youless delivery meter value sensor."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: DataUpdateCoordinator[YoulessAPI], device: str, dev_type: str
    ) -> None:
        """Instantiate a delivery meter sensor."""
        super().__init__(
            coordinator, device, "delivery", "Energy delivery", f"delivery_{dev_type}"
        )
        self._type = dev_type
        self._attr_name = f"Energy delivery {dev_type}"

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor for providing the value."""
        if self.coordinator.data.delivery_meter is None:
            return None

        return getattr(self.coordinator.data.delivery_meter, f"_{self._type}", None)


class EnergyMeterSensor(YoulessBaseSensor):
    """The Youless low meter value sensor."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[YoulessAPI],
        device: str,
        dev_type: str,
        state_class: SensorStateClass,
    ) -> None:
        """Instantiate a energy meter sensor."""
        super().__init__(
            coordinator, device, "power", "Energy usage", f"power_{dev_type}"
        )
        self._device = device
        self._type = dev_type
        self._attr_name = f"Energy {dev_type}"
        self._attr_state_class = state_class

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor for providing the value."""
        if self.coordinator.data.power_meter is None:
            return None

        return getattr(self.coordinator.data.power_meter, f"_{self._type}", None)


class PhasePowerSensor(YoulessBaseSensor):
    """The current power usage of a single phase."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: DataUpdateCoordinator[YoulessAPI], device: str, phase: int
    ) -> None:
        """Initialize the power phase sensor."""
        super().__init__(
            coordinator, device, "power", "Energy usage", f"phase_{phase}_power"
        )
        self._attr_name = f"Phase {phase} power"
        self._phase = phase

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor value from the coordinator."""
        phase_sensor = getattr(self.coordinator.data, f"phase{self._phase}", None)
        if phase_sensor is None:
            return None

        return phase_sensor.power


class PhaseVoltageSensor(YoulessBaseSensor):
    """The current voltage of a single phase."""

    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: DataUpdateCoordinator[YoulessAPI], device: str, phase: int
    ) -> None:
        """Initialize the voltage phase sensor."""
        super().__init__(
            coordinator, device, "power", "Energy usage", f"phase_{phase}_voltage"
        )
        self._attr_name = f"Phase {phase} voltage"
        self._phase = phase

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor value from the coordinator for phase voltage."""
        phase_sensor = getattr(self.coordinator.data, f"phase{self._phase}", None)
        if phase_sensor is None:
            return None

        return phase_sensor.voltage


class PhaseCurrentSensor(YoulessBaseSensor):
    """The current current of a single phase."""

    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: DataUpdateCoordinator[YoulessAPI], device: str, phase: int
    ) -> None:
        """Initialize the current phase sensor."""
        super().__init__(
            coordinator, device, "power", "Energy usage", f"phase_{phase}_current"
        )
        self._attr_name = f"Phase {phase} current"
        self._phase = phase

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor value from the coordinator for phase current."""
        phase_sensor = getattr(self.coordinator.data, f"phase{self._phase}", None)
        if phase_sensor is None:
            return None

        return phase_sensor.current


class ExtraMeterSensor(YoulessBaseSensor):
    """The Youless extra meter value sensor (s0)."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: DataUpdateCoordinator[YoulessAPI], device: str, dev_type: str
    ) -> None:
        """Instantiate an extra meter sensor."""
        super().__init__(
            coordinator, device, "extra", "Extra meter", f"extra_{dev_type}"
        )
        self._type = dev_type
        self._attr_name = f"Extra {dev_type}"

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor for providing the value."""
        if self.coordinator.data.extra_meter is None:
            return None

        return getattr(self.coordinator.data.extra_meter, f"_{self._type}", None)


class ExtraMeterPowerSensor(YoulessBaseSensor):
    """The Youless extra meter power value sensor (s0)."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: DataUpdateCoordinator[YoulessAPI], device: str, dev_type: str
    ) -> None:
        """Instantiate an extra meter power sensor."""
        super().__init__(
            coordinator, device, "extra", "Extra meter", f"extra_{dev_type}"
        )
        self._type = dev_type
        self._attr_name = f"Extra {dev_type}"

    @property
    def get_sensor(self) -> YoulessSensor | None:
        """Get the sensor for providing the value."""
        if self.coordinator.data.extra_meter is None:
            return None

        return getattr(self.coordinator.data.extra_meter, f"_{self._type}", None)
