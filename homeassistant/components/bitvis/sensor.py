"""Sensor platform for Bitvis Power Hub."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from bitvis_protobuf.han_port_pb2 import HanPortSample
from bitvis_protobuf.powerhub_pb2 import Diagnostic

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from . import BitvisConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL_NAME
from .coordinator import BitvisDataUpdateCoordinator

PARALLEL_UPDATES = 0


def _uptime_to_datetime(value: int) -> datetime:
    """Convert uptime in seconds to a start datetime timestamp."""
    return utcnow().replace(microsecond=0) - timedelta(seconds=value)


uptime_to_stable_datetime = ignore_variance(_uptime_to_datetime, timedelta(minutes=5))


def _build_device_info(
    coordinator: BitvisDataUpdateCoordinator,
    device_identifier: str,
    title: str,
) -> DeviceInfo:
    """Build DeviceInfo shared by all Bitvis entities."""
    payload = coordinator.data.diagnostic
    mac_address: str | None = None
    model_name: str | None = None
    sw_version: str | None = None
    if payload is not None and payload.diagnostic.HasField("device_info"):
        mac_address = coordinator.data.mac_address or None
        model_name = payload.diagnostic.device_info.model_name or None
        sw_version = payload.diagnostic.device_info.sw_version or None
    return DeviceInfo(
        identifiers={(DOMAIN, device_identifier)},
        connections={(CONNECTION_NETWORK_MAC, mac_address)} if mac_address else set(),
        name=title,
        manufacturer=MANUFACTURER,
        model=model_name or MODEL_NAME,
        sw_version=sw_version,
    )


@dataclass(frozen=True, kw_only=True)
class BitvisSensorEntityDescription(SensorEntityDescription):
    """Describes Bitvis sensor entity."""

    value_fn: Callable[[HanPortSample], float | None]
    exists_fn: Callable[[HanPortSample], bool] = lambda x: True


@dataclass(frozen=True, kw_only=True)
class BitvisDiagnosticSensorEntityDescription(SensorEntityDescription):
    """Describes Bitvis diagnostic sensor entity."""

    value_fn: Callable[[Diagnostic], float | int | str | datetime | None]
    exists_fn: Callable[[Diagnostic], bool] = lambda x: True


SENSOR_DESCRIPTIONS: tuple[BitvisSensorEntityDescription, ...] = (
    # Phase voltages
    BitvisSensorEntityDescription(
        key="phase_voltage_l1",
        translation_key="phase_voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            data.phase_voltage_l1_v if data.HasField("phase_voltage_l1_v") else None
        ),
        exists_fn=lambda data: data.HasField("phase_voltage_l1_v"),
    ),
    BitvisSensorEntityDescription(
        key="phase_voltage_l2",
        translation_key="phase_voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            data.phase_voltage_l2_v if data.HasField("phase_voltage_l2_v") else None
        ),
        exists_fn=lambda data: data.HasField("phase_voltage_l2_v"),
    ),
    BitvisSensorEntityDescription(
        key="phase_voltage_l3",
        translation_key="phase_voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            data.phase_voltage_l3_v if data.HasField("phase_voltage_l3_v") else None
        ),
        exists_fn=lambda data: data.HasField("phase_voltage_l3_v"),
    ),
    # Phase currents
    BitvisSensorEntityDescription(
        key="phase_current_l1",
        translation_key="phase_current_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.phase_current_l1_a if data.HasField("phase_current_l1_a") else None
        ),
        exists_fn=lambda data: data.HasField("phase_current_l1_a"),
    ),
    BitvisSensorEntityDescription(
        key="phase_current_l2",
        translation_key="phase_current_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.phase_current_l2_a if data.HasField("phase_current_l2_a") else None
        ),
        exists_fn=lambda data: data.HasField("phase_current_l2_a"),
    ),
    BitvisSensorEntityDescription(
        key="phase_current_l3",
        translation_key="phase_current_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.phase_current_l3_a if data.HasField("phase_current_l3_a") else None
        ),
        exists_fn=lambda data: data.HasField("phase_current_l3_a"),
    ),
    # Total active power
    BitvisSensorEntityDescription(
        key="power_active_delivered_to_client",
        translation_key="power_active_delivered_to_client",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_active_delivered_to_client_kw
            if data.HasField("power_active_delivered_to_client_kw")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_active_delivered_to_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_delivered_by_client",
        translation_key="power_active_delivered_by_client",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_active_delivered_by_client_kw
            if data.HasField("power_active_delivered_by_client_kw")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_active_delivered_by_client_kw"),
    ),
    # Total reactive power
    BitvisSensorEntityDescription(
        key="power_reactive_delivered_to_client",
        translation_key="power_reactive_delivered_to_client",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_reactive_delivered_to_client_kvar
            if data.HasField("power_reactive_delivered_to_client_kvar")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_reactive_delivered_to_client_kvar"),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_delivered_by_client",
        translation_key="power_reactive_delivered_by_client",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_reactive_delivered_by_client_kvar
            if data.HasField("power_reactive_delivered_by_client_kvar")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_reactive_delivered_by_client_kvar"),
    ),
    # Per-phase active power (to client)
    BitvisSensorEntityDescription(
        key="power_active_l1_delivered_to_client",
        translation_key="power_active_l1_delivered_to_client",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_active_l1_delivered_to_client_kw
            if data.HasField("power_active_l1_delivered_to_client_kw")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_active_l1_delivered_to_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_l2_delivered_to_client",
        translation_key="power_active_l2_delivered_to_client",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_active_l2_delivered_to_client_kw
            if data.HasField("power_active_l2_delivered_to_client_kw")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_active_l2_delivered_to_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_l3_delivered_to_client",
        translation_key="power_active_l3_delivered_to_client",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_active_l3_delivered_to_client_kw
            if data.HasField("power_active_l3_delivered_to_client_kw")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_active_l3_delivered_to_client_kw"),
    ),
    # Per-phase active power (by client)
    BitvisSensorEntityDescription(
        key="power_active_l1_delivered_by_client",
        translation_key="power_active_l1_delivered_by_client",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_active_l1_delivered_by_client_kw
            if data.HasField("power_active_l1_delivered_by_client_kw")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_active_l1_delivered_by_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_l2_delivered_by_client",
        translation_key="power_active_l2_delivered_by_client",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_active_l2_delivered_by_client_kw
            if data.HasField("power_active_l2_delivered_by_client_kw")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_active_l2_delivered_by_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_l3_delivered_by_client",
        translation_key="power_active_l3_delivered_by_client",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_active_l3_delivered_by_client_kw
            if data.HasField("power_active_l3_delivered_by_client_kw")
            else None
        ),
        exists_fn=lambda data: data.HasField("power_active_l3_delivered_by_client_kw"),
    ),
    # Per-phase reactive power (to client)
    BitvisSensorEntityDescription(
        key="power_reactive_l1_delivered_to_client",
        translation_key="power_reactive_l1_delivered_to_client",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_reactive_l1_delivered_to_client_kvar
            if data.HasField("power_reactive_l1_delivered_to_client_kvar")
            else None
        ),
        exists_fn=lambda data: data.HasField(
            "power_reactive_l1_delivered_to_client_kvar"
        ),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_l2_delivered_to_client",
        translation_key="power_reactive_l2_delivered_to_client",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_reactive_l2_delivered_to_client_kvar
            if data.HasField("power_reactive_l2_delivered_to_client_kvar")
            else None
        ),
        exists_fn=lambda data: data.HasField(
            "power_reactive_l2_delivered_to_client_kvar"
        ),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_l3_delivered_to_client",
        translation_key="power_reactive_l3_delivered_to_client",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_reactive_l3_delivered_to_client_kvar
            if data.HasField("power_reactive_l3_delivered_to_client_kvar")
            else None
        ),
        exists_fn=lambda data: data.HasField(
            "power_reactive_l3_delivered_to_client_kvar"
        ),
    ),
    # Per-phase reactive power (by client)
    BitvisSensorEntityDescription(
        key="power_reactive_l1_delivered_by_client",
        translation_key="power_reactive_l1_delivered_by_client",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_reactive_l1_delivered_by_client_kvar
            if data.HasField("power_reactive_l1_delivered_by_client_kvar")
            else None
        ),
        exists_fn=lambda data: data.HasField(
            "power_reactive_l1_delivered_by_client_kvar"
        ),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_l2_delivered_by_client",
        translation_key="power_reactive_l2_delivered_by_client",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_reactive_l2_delivered_by_client_kvar
            if data.HasField("power_reactive_l2_delivered_by_client_kvar")
            else None
        ),
        exists_fn=lambda data: data.HasField(
            "power_reactive_l2_delivered_by_client_kvar"
        ),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_l3_delivered_by_client",
        translation_key="power_reactive_l3_delivered_by_client",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: (
            data.power_reactive_l3_delivered_by_client_kvar
            if data.HasField("power_reactive_l3_delivered_by_client_kvar")
            else None
        ),
        exists_fn=lambda data: data.HasField(
            "power_reactive_l3_delivered_by_client_kvar"
        ),
    ),
    # Energy - active
    BitvisSensorEntityDescription(
        key="energy_active_delivered_to_client",
        translation_key="energy_active_delivered_to_client",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.energy_active_delivered_to_client_kwh
            if data.HasField("energy_active_delivered_to_client_kwh")
            else None
        ),
        exists_fn=lambda data: data.HasField("energy_active_delivered_to_client_kwh"),
    ),
    BitvisSensorEntityDescription(
        key="energy_active_delivered_by_client",
        translation_key="energy_active_delivered_by_client",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.energy_active_delivered_by_client_kwh
            if data.HasField("energy_active_delivered_by_client_kwh")
            else None
        ),
        exists_fn=lambda data: data.HasField("energy_active_delivered_by_client_kwh"),
    ),
    # Energy - reactive
    BitvisSensorEntityDescription(
        key="energy_reactive_delivered_to_client",
        translation_key="energy_reactive_delivered_to_client",
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        native_unit_of_measurement=UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.energy_reactive_delivered_to_client_kvarh
            if data.HasField("energy_reactive_delivered_to_client_kvarh")
            else None
        ),
        exists_fn=lambda data: data.HasField(
            "energy_reactive_delivered_to_client_kvarh"
        ),
    ),
    BitvisSensorEntityDescription(
        key="energy_reactive_delivered_by_client",
        translation_key="energy_reactive_delivered_by_client",
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        native_unit_of_measurement=UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.energy_reactive_delivered_by_client_kvarh
            if data.HasField("energy_reactive_delivered_by_client_kvarh")
            else None
        ),
        exists_fn=lambda data: data.HasField(
            "energy_reactive_delivered_by_client_kvarh"
        ),
    ),
)

DIAGNOSTIC_SENSOR_DESCRIPTIONS: tuple[BitvisDiagnosticSensorEntityDescription, ...] = (
    BitvisDiagnosticSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: uptime_to_stable_datetime(data.uptime_s),
        exists_fn=lambda data: True,
    ),
    BitvisDiagnosticSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wifi_rssi_dbm,
        exists_fn=lambda data: True,
    ),
    BitvisDiagnosticSensorEntityDescription(
        key="han_msg_successfully_parsed",
        translation_key="han_msg_successfully_parsed",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.han_msg_successfully_parsed,
        exists_fn=lambda data: True,
    ),
    BitvisDiagnosticSensorEntityDescription(
        key="han_msg_buffer_overflow",
        translation_key="han_msg_buffer_overflow",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.han_msg_buffer_overflow,
        exists_fn=lambda data: True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitvisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bitvis sensor platform."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        BitvisSensorEntity(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    ]

    entities.extend(
        BitvisDiagnosticSensorEntity(coordinator, description, entry)
        for description in DIAGNOSTIC_SENSOR_DESCRIPTIONS
    )

    async_add_entities(entities)


class BitvisSensorEntity(CoordinatorEntity[BitvisDataUpdateCoordinator], SensorEntity):
    """Representation of a Bitvis sensor."""

    entity_description: BitvisSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BitvisDataUpdateCoordinator,
        description: BitvisSensorEntityDescription,
        entry: BitvisConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_identifier = entry.unique_id or entry.entry_id
        self._entry_title = entry.title
        self._attr_unique_id = f"{self._device_identifier}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return _build_device_info(
            self.coordinator, self._device_identifier, self._entry_title
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data.sample is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data.sample.sample)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data.sample is not None
            and self.entity_description.exists_fn(self.coordinator.data.sample.sample)
        )


class BitvisDiagnosticSensorEntity(
    CoordinatorEntity[BitvisDataUpdateCoordinator], SensorEntity
):
    """Representation of a Bitvis diagnostic sensor."""

    entity_description: BitvisDiagnosticSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BitvisDataUpdateCoordinator,
        description: BitvisDiagnosticSensorEntityDescription,
        entry: BitvisConfigEntry,
    ) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_identifier = entry.unique_id or entry.entry_id
        self._entry_title = entry.title
        self._attr_unique_id = f"{self._device_identifier}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return _build_device_info(
            self.coordinator, self._device_identifier, self._entry_title
        )

    @property
    def native_value(self) -> float | int | str | datetime | None:
        """Return the state of the sensor."""
        if self.coordinator.data.diagnostic is None:
            return None
        return self.entity_description.value_fn(
            self.coordinator.data.diagnostic.diagnostic
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data.diagnostic is not None
            and self.entity_description.exists_fn(
                self.coordinator.data.diagnostic.diagnostic
            )
        )
