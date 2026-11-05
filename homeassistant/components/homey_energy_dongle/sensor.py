"""Sensors for the Homey Energy Dongle."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Any, override

from dsmr_parser.objects import MbusDevice, Telegram

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DSMR_VERSION, DOMAIN
from .coordinator import (
    HomeyEnergyDongleConfigEntry,
    HomeyEnergyDongleCoordinator,
    mbus_equipment_identifier,
    meter_identifier,
    meters,
)

PARALLEL_UPDATES = 0

PHASES = ("1", "2", "3")
TARIFFS = ("1", "2", "3", "4")

# Belgian and Hungarian meters use register 1 for the high tariff.
_TARIFF_HIGH_FIRST = frozenset({"5B", "5EONHU"})


@dataclass(frozen=True, kw_only=True)
class HomeyEnergyDongleSensorEntityDescription(SensorEntityDescription):
    """Describe a sensor that reads from a DSMR telegram or M-Bus device."""

    value_fn: Callable[[Telegram | MbusDevice], StateType | datetime | Decimal]
    dsmr_versions: frozenset[str] | None = None


def _value(data: Telegram | MbusDevice, ref: str) -> Any:
    """Return a register's value, or None when the telegram lacks it."""
    obj = getattr(data, ref, None)
    return None if obj is None else obj.value


def _register_watts(data: Telegram | MbusDevice, ref: str) -> Decimal | None:
    """Return a power register in watts; Q3D meters report W, the others kW."""
    if (obj := getattr(data, ref, None)) is None:
        return None
    value = Decimal(obj.value)
    return value if obj.unit == UnitOfPower.WATT else value * 1000


def _watts(data: Telegram | MbusDevice, ref: str) -> Decimal | None:
    """Return a power register in watts; the field resolves to 1 W."""
    value = _register_watts(data, ref)
    return None if value is None else value.to_integral_value()


def _power(data: Telegram | MbusDevice, positive: str, negative: str) -> Decimal | None:
    """Return import minus export in watts, treating a missing side as zero."""
    pos, neg = _register_watts(data, positive), _register_watts(data, negative)
    if pos is None and neg is None:
        return None
    return ((pos or Decimal(0)) - (neg or Decimal(0))).to_integral_value()


def _total(
    data: Telegram | MbusDevice, total: str, tariffs: tuple[str, ...]
) -> Decimal | None:
    """Prefer the meter's total register, else sum the tariff registers.

    A sum without one of the registers drops, and the statistics count a drop
    as a meter reset, so a telegram missing one gives no value.
    """
    if (value := _value(data, total)) is not None:
        return Decimal(value)
    values = [_value(data, ref) for ref in tariffs]
    if None in values:
        return None
    return Decimal(sum(values))


def _tariff(data: Telegram | MbusDevice, states: dict[str, str]) -> str | None:
    """Map the active tariff code to its state."""
    return states.get(_value(data, "ELECTRICITY_ACTIVE_TARIFF"))


def _tariff_registers(data: Telegram) -> set[str]:
    """Return tariff numbers present on the import or export register."""
    return {
        tariff
        for tariff in TARIFFS
        if _value(data, f"ELECTRICITY_USED_TARIFF_{tariff}") is not None
        or _value(data, f"ELECTRICITY_DELIVERED_TARIFF_{tariff}") is not None
    }


def _with_tariff_name(
    description: HomeyEnergyDongleSensorEntityDescription,
    *,
    numbered: bool,
    high_first: bool,
) -> HomeyEnergyDongleSensorEntityDescription:
    """Match Homey's high and low titles when the meter has only two tariffs."""
    if numbered or not description.key.startswith(("import_tariff_", "export_tariff_")):
        return description
    tariff = description.key.rpartition("_")[2]
    if tariff not in ("1", "2"):
        return description
    direction = "imported" if description.key.startswith("import_") else "exported"
    kind = "high" if (tariff == "1") == high_first else "low"
    return replace(
        description,
        translation_key=f"total_energy_{direction}_{kind}",
        translation_placeholders=None,
    )


SENSORS: tuple[HomeyEnergyDongleSensorEntityDescription, ...] = (
    HomeyEnergyDongleSensorEntityDescription(
        key="p1_message_timestamp",
        translation_key="p1_message_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=partial(_value, ref="P1_MESSAGE_TIMESTAMP"),
    ),
    HomeyEnergyDongleSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=partial(
            _power,
            positive="CURRENT_ELECTRICITY_USAGE",
            negative="CURRENT_ELECTRICITY_DELIVERY",
        ),
    ),
    # Fluvius bills the capacity tariff on these two registers.
    HomeyEnergyDongleSensorEntityDescription(
        key="current_average_demand",
        translation_key="current_average_demand",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=partial(_watts, ref="BELGIUM_CURRENT_AVERAGE_DEMAND"),
    ),
    HomeyEnergyDongleSensorEntityDescription(
        key="maximum_demand_month",
        translation_key="maximum_demand_month",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=partial(_watts, ref="BELGIUM_MAXIMUM_DEMAND_MONTH"),
    ),
    HomeyEnergyDongleSensorEntityDescription(
        key="active_tariff",
        translation_key="active_tariff",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "high"],
        value_fn=partial(_tariff, states={"0001": "low", "0002": "high"}),
        dsmr_versions=frozenset({"2.2", "4", "5", "5L"}),
    ),
    # Belgian and Hungarian meters swap the tariff codes.
    HomeyEnergyDongleSensorEntityDescription(
        key="active_tariff",
        translation_key="active_tariff",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "high"],
        value_fn=partial(_tariff, states={"0001": "high", "0002": "low"}),
        dsmr_versions=_TARIFF_HIGH_FIRST,
    ),
    # Only meters without a total register sum their tariffs, and those profiles
    # (DSMR 2.2, 4 and 5B) have exactly two.
    HomeyEnergyDongleSensorEntityDescription(
        key="total_energy_imported",
        translation_key="total_energy_imported",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=partial(
            _total,
            total="ELECTRICITY_IMPORTED_TOTAL",
            tariffs=("ELECTRICITY_USED_TARIFF_1", "ELECTRICITY_USED_TARIFF_2"),
        ),
    ),
    HomeyEnergyDongleSensorEntityDescription(
        key="total_energy_exported",
        translation_key="total_energy_exported",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=partial(
            _total,
            total="ELECTRICITY_EXPORTED_TOTAL",
            tariffs=(
                "ELECTRICITY_DELIVERED_TARIFF_1",
                "ELECTRICITY_DELIVERED_TARIFF_2",
            ),
        ),
    ),
    *(
        HomeyEnergyDongleSensorEntityDescription(
            key=f"import_tariff_{tariff}",
            translation_key="total_energy_imported_tariff",
            translation_placeholders={"tariff": tariff},
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=3,
            value_fn=partial(_value, ref=f"ELECTRICITY_USED_TARIFF_{tariff}"),
        )
        for tariff in TARIFFS
    ),
    *(
        HomeyEnergyDongleSensorEntityDescription(
            key=f"export_tariff_{tariff}",
            translation_key="total_energy_exported_tariff",
            translation_placeholders={"tariff": tariff},
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=3,
            value_fn=partial(_value, ref=f"ELECTRICITY_DELIVERED_TARIFF_{tariff}"),
        )
        for tariff in TARIFFS
    ),
    HomeyEnergyDongleSensorEntityDescription(
        key="long_power_failure_count",
        translation_key="long_power_failure_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=partial(_value, ref="LONG_POWER_FAILURE_COUNT"),
    ),
    HomeyEnergyDongleSensorEntityDescription(
        key="short_power_failure_count",
        translation_key="short_power_failure_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=partial(_value, ref="SHORT_POWER_FAILURE_COUNT"),
    ),
    *(
        HomeyEnergyDongleSensorEntityDescription(
            key=f"voltage_phase_{phase}",
            translation_key="voltage_phase",
            translation_placeholders={"phase": phase},
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=1,
            value_fn=partial(_value, ref=f"INSTANTANEOUS_VOLTAGE_L{phase}"),
        )
        for phase in PHASES
    ),
    *(
        HomeyEnergyDongleSensorEntityDescription(
            key=f"current_phase_{phase}",
            translation_key="current_phase",
            translation_placeholders={"phase": phase},
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            value_fn=partial(_value, ref=f"INSTANTANEOUS_CURRENT_L{phase}"),
        )
        for phase in PHASES
    ),
    *(
        HomeyEnergyDongleSensorEntityDescription(
            key=f"power_phase_{phase}",
            translation_key="power_phase",
            translation_placeholders={"phase": phase},
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=0,
            value_fn=partial(
                _power,
                positive=f"INSTANTANEOUS_ACTIVE_POWER_L{phase}_POSITIVE",
                negative=f"INSTANTANEOUS_ACTIVE_POWER_L{phase}_NEGATIVE",
            ),
        )
        for phase in PHASES
    ),
    *(
        HomeyEnergyDongleSensorEntityDescription(
            key=f"voltage_sag_count_phase_{phase}",
            translation_key="voltage_sag_count_phase",
            translation_placeholders={"phase": phase},
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=partial(_value, ref=f"VOLTAGE_SAG_L{phase}_COUNT"),
        )
        for phase in PHASES
    ),
    *(
        HomeyEnergyDongleSensorEntityDescription(
            key=f"voltage_swell_count_phase_{phase}",
            translation_key="voltage_swell_count_phase",
            translation_placeholders={"phase": phase},
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=partial(_value, ref=f"VOLTAGE_SWELL_L{phase}_COUNT"),
        )
        for phase in PHASES
    ),
)

# M-Bus device types from EN 13757-3, with the device translation key.
MBUS_SENSORS: dict[int, tuple[str, HomeyEnergyDongleSensorEntityDescription]] = {
    device_type: (
        device_key,
        HomeyEnergyDongleSensorEntityDescription(
            key="meter_reading",
            translation_key="meter_reading",
            device_class=device_class,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_display_precision=3,
            value_fn=partial(_value, ref="MBUS_METER_READING"),
        ),
    )
    for device_type, device_key, device_class in (
        (3, "gas_meter", SensorDeviceClass.GAS),
        (4, "heat_meter", SensorDeviceClass.ENERGY),
        (7, "water_meter", SensorDeviceClass.WATER),
    )
}


def _with_mbus_unit(
    description: HomeyEnergyDongleSensorEntityDescription, device: MbusDevice
) -> HomeyEnergyDongleSensorEntityDescription:
    """Apply the unit the meter reports; some gas meters report energy."""
    unit = device.MBUS_METER_READING.unit
    if unit == "m3":
        unit = UnitOfVolume.CUBIC_METERS
    if unit in UnitOfEnergy:
        return replace(
            description,
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=unit,
        )
    return replace(description, native_unit_of_measurement=unit)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeyEnergyDongleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a sensor for each register of each meter once it is in a telegram."""
    coordinator = entry.runtime_data
    dsmr_version = entry.data[CONF_DSMR_VERSION]
    high_first = dsmr_version in _TARIFF_HIGH_FIRST

    dongle_id = dr.async_get_device_id_by_identifier(
        hass, (DOMAIN, entry.entry_id), config_entry_id=entry.entry_id
    )
    descriptions = [
        description
        for description in SENSORS
        if description.dsmr_versions is None
        or dsmr_version in description.dsmr_versions
    ]
    added: dict[str, set[str]] = {}

    @callback
    def _async_add_new_entities() -> None:
        entities: list[HomeyEnergyDongleSensor] = []
        for serial, data in meters(coordinator.data, entry).items():
            if isinstance(data, MbusDevice):
                mbus = MBUS_SENSORS.get(_value(data, "MBUS_DEVICE_TYPE"))
                if mbus is None:
                    continue
                device_key, description = mbus
                identifier = mbus_equipment_identifier(data)
                candidates = (
                    [_with_mbus_unit(description, data)]
                    if description.value_fn(data) is not None
                    else []
                )
            else:
                device_key = "electricity_meter"
                identifier = meter_identifier(data)
                numbered = len(_tariff_registers(data)) > 2
                candidates = [
                    _with_tariff_name(d, numbered=numbered, high_first=high_first)
                    for d in descriptions
                ]
            keys = added.setdefault(serial, set())
            device_info = dr.DeviceInfo(
                identifiers={(DOMAIN, serial)},
                serial_number=identifier,
                translation_key=device_key,
                via_device_id=dongle_id,
            )
            for description in candidates:
                if description.key in keys or description.value_fn(data) is None:
                    continue
                keys.add(description.key)
                entities.append(
                    HomeyEnergyDongleSensor(
                        coordinator, description, serial, device_info
                    )
                )

        if entities:
            async_add_entities(entities)

    @callback
    def _async_forget_removed_meter(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        """Let a deleted meter be added again when it reappears."""
        if event.data["action"] == "remove":
            for domain, identifier in event.data["device"]["identifiers"]:
                if domain == DOMAIN:
                    added.pop(identifier, None)

    _async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    entry.async_on_unload(
        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, _async_forget_removed_meter
        )
    )


class HomeyEnergyDongleSensor(
    CoordinatorEntity[HomeyEnergyDongleCoordinator], SensorEntity
):
    """Sensor reading one value from the latest telegram."""

    _attr_has_entity_name = True
    entity_description: HomeyEnergyDongleSensorEntityDescription

    def __init__(
        self,
        coordinator: HomeyEnergyDongleCoordinator,
        description: HomeyEnergyDongleSensorEntityDescription,
        serial: str,
        device_info: dr.DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = device_info
        self._serial = serial

    @property
    def _meter(self) -> Telegram | MbusDevice | None:
        """Return the readings of this sensor's meter in the latest telegram."""
        return meters(self.coordinator.data, self.coordinator.config_entry).get(
            self._serial
        )

    @property
    @override
    def available(self) -> bool:
        """Return if this sensor's meter is in the latest telegram."""
        return super().available and self._meter is not None

    @property
    @override
    def native_value(self) -> StateType | datetime | Decimal:
        """Return the value of this sensor's meter in the latest telegram."""
        data = self._meter
        if TYPE_CHECKING:
            assert data is not None
        value = self.entity_description.value_fn(data)
        # A meter briefly reporting 0 would reset the long-term statistics.
        if (
            not value
            and self.state_class is SensorStateClass.TOTAL_INCREASING
            and self.device_class is not None
        ):
            return None
        return value
