"""Support for iammeter via local API."""

from __future__ import annotations

from asyncio import timeout
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from iammeter.client import IamMeter
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import (
    config_validation as cv,
    debounce,
    entity_registry as er,
    update_coordinator,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEVICE_3080, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_DEVICE_NAME = "IamMeter"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_DEVICE_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

SCAN_INTERVAL = timedelta(seconds=30)
PLATFORM_TIMEOUT = 8


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
    phase_list = ["A", "B", "C", "NET"]
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
            entity_id = ent_reg.async_get_entity_id(
                Platform.SENSOR, DOMAIN, old_unique_id
            )
            if entity_id is not None:
                try:
                    ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
                except ValueError:
                    _LOGGER.warning(
                        "Skip migration of id [%s] to [%s] because it already exists",
                        old_unique_id,
                        new_unique_id,
                    )
                else:
                    _LOGGER.debug(
                        "Migrating unique_id from [%s] to [%s]",
                        old_unique_id,
                        new_unique_id,
                    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Platform setup."""
    config_host = config[CONF_HOST]
    config_port = config[CONF_PORT]
    config_name = config[CONF_NAME]
    try:
        api = await hass.async_add_executor_job(
            IamMeter, config_host, config_port, config_name
        )
    except TimeoutError as err:
        _LOGGER.error("Device is not ready")
        raise PlatformNotReady from err

    async def async_update_data():
        try:
            async with timeout(PLATFORM_TIMEOUT):
                return await hass.async_add_executor_job(api.client.get_data)
        except TimeoutError as err:
            raise UpdateFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=config_name,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=0.3, immediate=True
        ),
    )
    await coordinator.async_refresh()
    model = coordinator.data["Model"]
    serial_number = coordinator.data["sn"]
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


class IammeterSensor(update_coordinator.CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: IammeterSensorEntityDescription
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: IammeterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data['sn']}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data["sn"])},
            manufacturer="IamMeter",
            name=coordinator.name,
        )

    @property
    def native_value(self):
        """Return the native sensor value."""
        raw_attr = self.coordinator.data.get(self.entity_description.key, None)
        if self.entity_description.value:
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
