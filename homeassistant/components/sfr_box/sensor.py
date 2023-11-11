"""SFR Box sensor platform."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from sfrbox_api.models import DslInfo, SystemInfo, WanInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfDataRate,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SFRDataUpdateCoordinator
from .models import DomainData

_T = TypeVar("_T")


@dataclass
class SFRBoxSensorMixin(Generic[_T]):
    """Mixin for SFR Box sensors."""

    value_fn: Callable[[_T], StateType]


@dataclass
class SFRBoxSensorEntityDescription(SensorEntityDescription, SFRBoxSensorMixin[_T]):
    """Description for SFR Box sensors."""


DSL_SENSOR_TYPES: tuple[SFRBoxSensorEntityDescription[DslInfo], ...] = (
    SFRBoxSensorEntityDescription[DslInfo](
        key="linemode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="dsl_linemode",
        value_fn=lambda x: x.linemode,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="dsl_counter",
        value_fn=lambda x: x.counter,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="crc",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="dsl_crc",
        value_fn=lambda x: x.crc,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="noise_down",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="dsl_noise_down",
        value_fn=lambda x: x.noise_down,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="noise_up",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="dsl_noise_up",
        value_fn=lambda x: x.noise_up,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="attenuation_down",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="dsl_attenuation_down",
        value_fn=lambda x: x.attenuation_down,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="attenuation_up",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="dsl_attenuation_up",
        value_fn=lambda x: x.attenuation_up,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="rate_down",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="dsl_rate_down",
        value_fn=lambda x: x.rate_down,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="rate_up",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="dsl_rate_up",
        value_fn=lambda x: x.rate_up,
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="line_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[
            "no_defect",
            "of_frame",
            "loss_of_signal",
            "loss_of_power",
            "loss_of_signal_quality",
            "unknown",
        ],
        translation_key="dsl_line_status",
        value_fn=lambda x: x.line_status.lower().replace(" ", "_"),
    ),
    SFRBoxSensorEntityDescription[DslInfo](
        key="training",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[
            "idle",
            "g_994_training",
            "g_992_started",
            "g_922_channel_analysis",
            "g_992_message_exchange",
            "g_993_started",
            "g_993_channel_analysis",
            "g_993_message_exchange",
            "showtime",
            "unknown",
        ],
        translation_key="dsl_training",
        value_fn=lambda x: x.training.lower().replace(" ", "_").replace(".", "_"),
    ),
)
SYSTEM_SENSOR_TYPES: tuple[SFRBoxSensorEntityDescription[SystemInfo], ...] = (
    SFRBoxSensorEntityDescription[SystemInfo](
        key="net_infra",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[
            "adsl",
            "ftth",
            "gprs",
            "unknown",
        ],
        translation_key="net_infra",
        value_fn=lambda x: x.net_infra,
    ),
    SFRBoxSensorEntityDescription[SystemInfo](
        key="alimvoltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value_fn=lambda x: x.alimvoltage,
    ),
    SFRBoxSensorEntityDescription[SystemInfo](
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda x: x.temperature / 1000,
    ),
)
WAN_SENSOR_TYPES: tuple[SFRBoxSensorEntityDescription[WanInfo], ...] = (
    SFRBoxSensorEntityDescription[WanInfo](
        key="mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[
            "adsl_ppp",
            "adsl_routed",
            "ftth_routed",
            "grps_ppp",
            "unknown",
        ],
        translation_key="wan_mode",
        value_fn=lambda x: x.mode.replace("/", "_"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    data: DomainData = hass.data[DOMAIN][entry.entry_id]

    entities: list[SFRBoxSensor] = [
        SFRBoxSensor(data.system, description, data.system.data)
        for description in SYSTEM_SENSOR_TYPES
    ]
    entities.extend(
        SFRBoxSensor(data.wan, description, data.system.data)
        for description in WAN_SENSOR_TYPES
    )
    if data.system.data.net_infra == "adsl":
        entities.extend(
            SFRBoxSensor(data.dsl, description, data.system.data)
            for description in DSL_SENSOR_TYPES
        )

    async_add_entities(entities)


class SFRBoxSensor(CoordinatorEntity[SFRDataUpdateCoordinator[_T]], SensorEntity):
    """SFR Box sensor."""

    entity_description: SFRBoxSensorEntityDescription[_T]
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SFRDataUpdateCoordinator[_T],
        description: SFRBoxSensorEntityDescription,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{system_info.mac_addr}_{coordinator.name}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_info.mac_addr)},
        )

    @property
    def native_value(self) -> StateType:
        """Return the native value of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
