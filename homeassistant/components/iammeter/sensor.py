"""IAMMETER physical, NET and reactive sensors."""

from dataclasses import replace
import logging
from typing import override

import probatio
from yarl import URL

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
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
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

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .coordinator import (
    IammeterConfigEntry,
    IammeterDataUpdateCoordinator,
    meter_identity,
)

_LOGGER = logging.getLogger(__name__)
SINGLE_PHASE_MODELS = {"WEM3080", "WEM3162"}
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
    id_phase_range = 1 if model in SINGLE_PHASE_MODELS else 4
    id_name_range = 5 if model in SINGLE_PHASE_MODELS else 7
    for row in range(id_phase_range):
        for idx in range(id_name_range):
            old_unique_id = f"{serial_number}-{row}-{idx}"
            new_unique_id = (
                f"{serial_number}_{name_list[idx]}"
                if model in SINGLE_PHASE_MODELS
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
    """Add fields when first reported, without removing historical entities."""
    coordinator = entry.runtime_data
    model = coordinator.data["Model"]
    _migrate_to_new_unique_id(
        hass, model, entry.unique_id or meter_identity(coordinator.data)
    )
    identity = entry.unique_id or meter_identity(coordinator.data)
    registered_keys = {
        entity.unique_id.removeprefix(f"{identity}_")
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }
    added_keys: set[str] = set()

    @callback
    def async_add_discovered_sensors() -> None:
        descriptions = [
            description
            for description in SENSOR_TYPES_BY_MODEL[coordinator.data["Model"]]
            if (
                description.key in coordinator.data
                or description.key in registered_keys
            )
            and description.key not in added_keys
        ]
        added_keys.update(description.key for description in descriptions)
        async_add_entities(
            IammeterSensor(coordinator, description) for description in descriptions
        )

    async_add_discovered_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_add_discovered_sensors))


class IammeterSensor(CoordinatorEntity[IammeterDataUpdateCoordinator], SensorEntity):
    """A named measurement belonging to a stable config entry."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IammeterDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a translated sensor with device metadata."""
        super().__init__(coordinator)
        self.entity_description = description
        identity = coordinator.config_entry.unique_id or meter_identity(
            coordinator.data
        )
        self._attr_unique_id = f"{identity}_{description.key}"
        url = URL(coordinator.client.endpoint)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity)},
            manufacturer="IAMMETER",
            name=coordinator.name,
            model=coordinator.data["Model"],
            sw_version=coordinator.data.get("version"),
            serial_number=coordinator.data.get("sn"),
            configuration_url=str(
                url.with_path(url.path.removesuffix("/monitorjson") or "/").with_query(
                    None
                )
            ),
        )

    @property
    @override
    def available(self) -> bool:
        """Missing optional fields are unavailable rather than zero."""
        return (
            super().available and self.entity_description.key in self.coordinator.data
        )

    @property
    @override
    def native_value(self) -> float | int | None:
        return self.coordinator.data.get(self.entity_description.key)


BASE_DESCRIPTIONS = (
    SensorEntityDescription(
        key="Voltage",
        translation_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="Current",
        translation_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="Power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ImportEnergy",
        translation_key="import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="ExportGrid",
        translation_key="export_grid",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="Frequency",
        translation_key="frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="PF",
        translation_key="pf",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
)
REACTIVE_DESCRIPTIONS = (
    SensorEntityDescription(
        key="ReactivePower",
        translation_key="reactive_power",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="InductiveReactiveEnergy",
        translation_key="inductive_reactive_energy",
        native_unit_of_measurement=UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="CapacitiveReactiveEnergy",
        translation_key="capacitive_reactive_energy",
        native_unit_of_measurement=UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


def _phase_descriptions(phase: str) -> tuple[SensorEntityDescription, ...]:
    return tuple(
        replace(
            description,
            key=f"{description.key}_{phase}",
            translation_key=f"{description.translation_key}_{phase.lower()}",
        )
        for description in (*BASE_DESCRIPTIONS, *REACTIVE_DESCRIPTIONS)
    )


NET_DESCRIPTIONS = tuple(
    replace(
        description,
        key=f"{description.key}_Net",
        translation_key=f"{description.translation_key}_net",
    )
    for description in BASE_DESCRIPTIONS
    if description.key != "Current"
)
SENSOR_TYPES_3080 = (
    *BASE_DESCRIPTIONS[:5],
    *tuple(
        replace(description, key=f"{description.key}_A")
        for description in REACTIVE_DESCRIPTIONS
    ),
)
SENSOR_TYPES_3080T = (
    *_phase_descriptions("A"),
    *_phase_descriptions("B"),
    *_phase_descriptions("C"),
    *NET_DESCRIPTIONS,
)
SENSOR_TYPES_2067 = (
    *_phase_descriptions("A"),
    *_phase_descriptions("B"),
    *NET_DESCRIPTIONS,
)
SENSOR_TYPES_BY_MODEL = dict.fromkeys(
    ("WEM3080T", "WEM3046T", "WEM3050T", "WEM3063T"), SENSOR_TYPES_3080T
)
SENSOR_TYPES_BY_MODEL.update(
    {
        "WEM3080": SENSOR_TYPES_3080,
        "WEM3162": SENSOR_TYPES_3080,
        "WEM2067": SENSOR_TYPES_2067,
    }
)
