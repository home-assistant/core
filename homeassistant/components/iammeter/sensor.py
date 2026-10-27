"""Support for iammeter via local API."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import override

import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    PERCENTAGE,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DEFAULT_PORT, DEVICE_2067, DEVICE_3080, DOMAIN
from .coordinator import IammeterConfigEntry, IammeterDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
    }
)


def _migrate_to_new_unique_id(
    hass: HomeAssistant, model: str, serial_number: str
) -> None:
    """Migrate old unique ids to new unique ids."""
    ent_reg = er.async_get(hass)
    name_list = [
        "Voltage",
        "Current",
        "Power",
        "ImportEnergy",
        "ExportGrid",
        "Frequency",
        "PF",
    ]
    phase_list = ["A", "B", "C", "Net"]
    id_phase_range = 1 if model == DEVICE_3080 else 4
    id_name_range = 5 if model == DEVICE_3080 else 7
    for row in range(id_phase_range):
        for idx in range(id_name_range):
            old_unique_id = f"{serial_number}-{row}-{idx}"
            new_unique_id = (
                f"{serial_number}_{name_list[idx]}"
                if model == DEVICE_3080
                else f"{serial_number}_{name_list[idx]}_{phase_list[row]}"
            )
            old_unique_ids = [old_unique_id]
            if row == 3:
                old_unique_ids.append(f"{serial_number}_{name_list[idx]}_NET")
            for previous_id in old_unique_ids:
                entity_id = ent_reg.async_get_entity_id(
                    Platform.SENSOR, DOMAIN, previous_id
                )
                if entity_id is None:
                    continue
                try:
                    ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
                except ValueError:
                    _LOGGER.warning(
                        "Skip migration of id [%s] to [%s] because it already exists",
                        previous_id,
                        new_unique_id,
                    )
                else:
                    _LOGGER.debug(
                        "Migrating unique_id from [%s] to [%s]",
                        previous_id,
                        new_unique_id,
                    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import a YAML sensor platform and retry if the meter is offline."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
    )
    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
        raise PlatformNotReady("Unable to import IAMMETER; check the meter connection")
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={"domain": DOMAIN, "integration_title": DEFAULT_NAME},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IammeterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IAMMETER sensors from a config entry."""
    coordinator = entry.runtime_data
    model = coordinator.data["Model"]
    serial_number = coordinator.data["sn"]
    if model == DEVICE_2067:
        added_keys: set[str] = set()

        @callback
        def async_add_discovered_sensors() -> None:
            """Add optional NET sensors when the meter first reports them."""
            descriptions = [
                description
                for description in SENSOR_TYPES_2067
                if description.key in coordinator.data
                and description.key not in added_keys
            ]
            if not descriptions:
                return
            added_keys.update(description.key for description in descriptions)
            async_add_entities(
                IammeterSensor(coordinator, description) for description in descriptions
            )

        async_add_discovered_sensors()
        entry.async_on_unload(
            coordinator.async_add_listener(async_add_discovered_sensors)
        )
        return

    _migrate_to_new_unique_id(hass, model, serial_number)
    if model == DEVICE_3080:
        async_add_entities(
            IammeterSensor(coordinator, description)
            for description in SENSOR_TYPES_3080
        )
    else:  # DEVICE_3080T:
        async_add_entities(
            IammeterSensor(coordinator, description)
            for description in SENSOR_TYPES_3080T
        )


class IammeterSensor(CoordinatorEntity[IammeterDataUpdateCoordinator], SensorEntity):
    """Representation of a Sensor."""

    entity_description: IammeterSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IammeterDataUpdateCoordinator,
        description: IammeterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if coordinator.data["Model"] != DEVICE_2067:
            self._attr_name = None
        self._attr_unique_id = f"{coordinator.data['sn']}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data["sn"])},
            manufacturer="IamMeter",
            name=coordinator.name,
            model=DEVICE_2067 if coordinator.data["Model"] == DEVICE_2067 else None,
        )

    @property
    @override
    def available(self) -> bool:
        """Mark previously discovered dual-channel readings unavailable if absent."""
        return super().available and (
            self.coordinator.data["Model"] != DEVICE_2067
            or self.entity_description.key in self.coordinator.data
        )

    @property
    @override
    def native_value(self):
        """Return the native sensor value."""
        raw_attr = self.coordinator.data.get(self.entity_description.key, None)
        if raw_attr is not None and self.entity_description.value:
            return self.entity_description.value(raw_attr)
        return raw_attr


@dataclass(frozen=True)
class IammeterSensorEntityDescription(SensorEntityDescription):
    """Describes Iammeter sensor entity."""

    value: Callable[[float | int], float] | Callable[[datetime], datetime] | None = None


SENSOR_TYPES_3080: tuple[IammeterSensorEntityDescription, ...] = (
    IammeterSensorEntityDescription(
        key="Voltage",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Current",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Power",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)
SENSOR_TYPES_3080T: tuple[IammeterSensorEntityDescription, ...] = (
    IammeterSensorEntityDescription(
        key="Voltage_A",
        translation_key="voltage_a",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Current_A",
        translation_key="current_a",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Power_A",
        translation_key="power_a",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy_A",
        translation_key="import_energy_a",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid_A",
        translation_key="export_grid_a",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IammeterSensorEntityDescription(
        key="Frequency_A",
        translation_key="frequency_a",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="PF_A",
        translation_key="pf_a",
        icon="mdi:solar-power",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value=lambda value: value * 100,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Voltage_B",
        translation_key="voltage_b",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Current_B",
        translation_key="current_b",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Power_B",
        translation_key="power_b",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy_B",
        translation_key="import_energy_b",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid_B",
        translation_key="export_grid_b",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IammeterSensorEntityDescription(
        key="Frequency_B",
        translation_key="frequency_b",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="PF_B",
        translation_key="pf_b",
        icon="mdi:solar-power",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value=lambda value: value * 100,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Voltage_C",
        translation_key="voltage_c",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Current_C",
        translation_key="current_c",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Power_C",
        translation_key="power_c",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy_C",
        translation_key="import_energy_c",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid_C",
        translation_key="export_grid_c",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IammeterSensorEntityDescription(
        key="Frequency_C",
        translation_key="frequency_c",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="PF_C",
        translation_key="pf_c",
        icon="mdi:solar-power",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value=lambda value: value * 100,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Voltage_Net",
        translation_key="voltage_net",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Power_Net",
        translation_key="power_net",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy_Net",
        translation_key="import_energy_net",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid_Net",
        translation_key="export_grid_net",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="Frequency_Net",
        translation_key="frequency_net",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IammeterSensorEntityDescription(
        key="PF_Net",
        translation_key="pf_net",
        icon="mdi:solar-power",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value=lambda value: value * 100,
        entity_registry_enabled_default=False,
    ),
)


SENSOR_TYPES_2067: tuple[IammeterSensorEntityDescription, ...] = tuple(
    description
    for description in SENSOR_TYPES_3080T
    if not description.key.endswith("_C")
)
