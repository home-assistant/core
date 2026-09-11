"""Sensor platform for Bitvis Power Hub."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast, override

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BitvisConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import BitvisDataUpdateCoordinator

PARALLEL_UPDATES = 0


def _optional(field: str) -> Callable[[HanPortSample], float | None]:
    """Return a getter that yields None when a protobuf field is unset."""

    def _get(data: HanPortSample) -> float | None:
        if data.HasField(field):
            return cast(float, getattr(data, field))
        return None

    return _get


@dataclass(frozen=True, kw_only=True)
class BitvisSensorEntityDescription(SensorEntityDescription):
    """Describes Bitvis sensor entity."""

    value_fn: Callable[[HanPortSample], float | None]


@dataclass(frozen=True, kw_only=True)
class BitvisDiagnosticSensorEntityDescription(SensorEntityDescription):
    """Describes Bitvis diagnostic sensor entity."""

    value_fn: Callable[[Diagnostic], float | int | str | datetime | None]


SENSOR_DESCRIPTIONS: tuple[BitvisSensorEntityDescription, ...] = (
    # Phase voltages
    BitvisSensorEntityDescription(
        key="phase_voltage_l1",
        translation_key="phase_voltage",
        translation_placeholders={"phase": "L1"},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_optional("phase_voltage_l1_v"),
    ),
    BitvisSensorEntityDescription(
        key="phase_voltage_l2",
        translation_key="phase_voltage",
        translation_placeholders={"phase": "L2"},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_optional("phase_voltage_l2_v"),
    ),
    BitvisSensorEntityDescription(
        key="phase_voltage_l3",
        translation_key="phase_voltage",
        translation_placeholders={"phase": "L3"},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_optional("phase_voltage_l3_v"),
    ),
    # Phase currents
    BitvisSensorEntityDescription(
        key="phase_current_l1",
        translation_key="phase_current",
        translation_placeholders={"phase": "L1"},
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_optional("phase_current_l1_a"),
    ),
    BitvisSensorEntityDescription(
        key="phase_current_l2",
        translation_key="phase_current",
        translation_placeholders={"phase": "L2"},
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_optional("phase_current_l2_a"),
    ),
    BitvisSensorEntityDescription(
        key="phase_current_l3",
        translation_key="phase_current",
        translation_placeholders={"phase": "L3"},
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_optional("phase_current_l3_a"),
    ),
    # Total active power
    BitvisSensorEntityDescription(
        key="power_active_delivered_to_client",
        translation_key="power_active_import",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_optional("power_active_delivered_to_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_delivered_by_client",
        translation_key="power_active_export",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_optional("power_active_delivered_by_client_kw"),
    ),
    # Total reactive power
    BitvisSensorEntityDescription(
        key="power_reactive_delivered_to_client",
        translation_key="power_reactive_import",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_reactive_delivered_to_client_kvar"),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_delivered_by_client",
        translation_key="power_reactive_export",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_reactive_delivered_by_client_kvar"),
    ),
    # Per-phase active power (to client)
    BitvisSensorEntityDescription(
        key="power_active_l1_delivered_to_client",
        translation_key="power_active_phase_import",
        translation_placeholders={"phase": "L1"},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_active_l1_delivered_to_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_l2_delivered_to_client",
        translation_key="power_active_phase_import",
        translation_placeholders={"phase": "L2"},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_active_l2_delivered_to_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_l3_delivered_to_client",
        translation_key="power_active_phase_import",
        translation_placeholders={"phase": "L3"},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_active_l3_delivered_to_client_kw"),
    ),
    # Per-phase active power (by client)
    BitvisSensorEntityDescription(
        key="power_active_l1_delivered_by_client",
        translation_key="power_active_phase_export",
        translation_placeholders={"phase": "L1"},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_active_l1_delivered_by_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_l2_delivered_by_client",
        translation_key="power_active_phase_export",
        translation_placeholders={"phase": "L2"},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_active_l2_delivered_by_client_kw"),
    ),
    BitvisSensorEntityDescription(
        key="power_active_l3_delivered_by_client",
        translation_key="power_active_phase_export",
        translation_placeholders={"phase": "L3"},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_active_l3_delivered_by_client_kw"),
    ),
    # Per-phase reactive power (to client)
    BitvisSensorEntityDescription(
        key="power_reactive_l1_delivered_to_client",
        translation_key="power_reactive_phase_import",
        translation_placeholders={"phase": "L1"},
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_reactive_l1_delivered_to_client_kvar"),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_l2_delivered_to_client",
        translation_key="power_reactive_phase_import",
        translation_placeholders={"phase": "L2"},
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_reactive_l2_delivered_to_client_kvar"),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_l3_delivered_to_client",
        translation_key="power_reactive_phase_import",
        translation_placeholders={"phase": "L3"},
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_reactive_l3_delivered_to_client_kvar"),
    ),
    # Per-phase reactive power (by client)
    BitvisSensorEntityDescription(
        key="power_reactive_l1_delivered_by_client",
        translation_key="power_reactive_phase_export",
        translation_placeholders={"phase": "L1"},
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_reactive_l1_delivered_by_client_kvar"),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_l2_delivered_by_client",
        translation_key="power_reactive_phase_export",
        translation_placeholders={"phase": "L2"},
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_reactive_l2_delivered_by_client_kvar"),
    ),
    BitvisSensorEntityDescription(
        key="power_reactive_l3_delivered_by_client",
        translation_key="power_reactive_phase_export",
        translation_placeholders={"phase": "L3"},
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
        value_fn=_optional("power_reactive_l3_delivered_by_client_kvar"),
    ),
    # Energy - active
    BitvisSensorEntityDescription(
        key="energy_active_delivered_to_client",
        translation_key="energy_active_import",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=_optional("energy_active_delivered_to_client_kwh"),
    ),
    BitvisSensorEntityDescription(
        key="energy_active_delivered_by_client",
        translation_key="energy_active_export",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=_optional("energy_active_delivered_by_client_kwh"),
    ),
    # Energy - reactive
    BitvisSensorEntityDescription(
        key="energy_reactive_delivered_to_client",
        translation_key="energy_reactive_import",
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        native_unit_of_measurement=UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=_optional("energy_reactive_delivered_to_client_kvarh"),
    ),
    BitvisSensorEntityDescription(
        key="energy_reactive_delivered_by_client",
        translation_key="energy_reactive_export",
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        native_unit_of_measurement=UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=_optional("energy_reactive_delivered_by_client_kvarh"),
    ),
)

UPTIME_DESCRIPTION = SensorEntityDescription(
    key="uptime",
    device_class=SensorDeviceClass.UPTIME,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)

DIAGNOSTIC_SENSOR_DESCRIPTIONS: tuple[BitvisDiagnosticSensorEntityDescription, ...] = (
    BitvisDiagnosticSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wifi_rssi_dbm,
    ),
    BitvisDiagnosticSensorEntityDescription(
        key="han_msg_successfully_parsed",
        translation_key="han_msg_successfully_parsed",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.han_msg_successfully_parsed,
    ),
    BitvisDiagnosticSensorEntityDescription(
        key="han_msg_buffer_overflow",
        translation_key="han_msg_buffer_overflow",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.han_msg_buffer_overflow,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitvisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bitvis sensor platform."""
    coordinator = entry.runtime_data
    known_keys: set[str] = set()

    async_add_entities(
        [
            BitvisUptimeSensorEntity(coordinator, UPTIME_DESCRIPTION),
            *(
                BitvisDiagnosticSensorEntity(coordinator, description)
                for description in DIAGNOSTIC_SENSOR_DESCRIPTIONS
            ),
        ]
    )

    @callback
    def _check_entities() -> None:
        if (payload := coordinator.data.sample) is None:
            return
        entities = [
            BitvisSensorEntity(coordinator, description)
            for description in SENSOR_DESCRIPTIONS
            if description.key not in known_keys
            and description.value_fn(payload.sample) is not None
        ]
        if entities:
            known_keys.update(entity.entity_description.key for entity in entities)
            async_add_entities(entities)

    _check_entities()
    entry.async_on_unload(coordinator.async_add_listener(_check_entities))


class BitvisBaseSensorEntity(
    CoordinatorEntity[BitvisDataUpdateCoordinator], SensorEntity
):
    """Base class for Bitvis sensor entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BitvisDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        mac_address = coordinator.mac_address
        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
            manufacturer=MANUFACTURER,
        )


class BitvisSensorEntity(BitvisBaseSensorEntity):
    """Representation of a Bitvis sensor."""

    entity_description: BitvisSensorEntityDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        payload = self.coordinator.data.sample
        if TYPE_CHECKING:
            assert payload is not None
        return self.entity_description.value_fn(payload.sample)

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.sample is not None


class BitvisDiagnosticSensorEntity(BitvisBaseSensorEntity):
    """Representation of a Bitvis diagnostic sensor."""

    entity_description: BitvisDiagnosticSensorEntityDescription

    @property
    @override
    def native_value(self) -> float | int | str | datetime | None:
        """Return the state of the sensor."""
        payload = self.coordinator.data.diagnostic
        if TYPE_CHECKING:
            assert payload is not None
        return self.entity_description.value_fn(payload.diagnostic)

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.diagnostic is not None


class BitvisUptimeSensorEntity(BitvisBaseSensorEntity):
    """Sensor entity for device uptime (boot time)."""

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the stable boot time computed by the coordinator."""
        return self.coordinator.data.boot_time

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.boot_time is not None
