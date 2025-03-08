"""Sensor platform for the Airios integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, cast, final

from pyairios import BRDG02R13
from pyairios.constants import (
    ProductId,
    ResetMode,
    VMDBypassPosition,
    VMDErrorCode,
    VMDHeater,
    VMDHeaterStatus,
    VMDSensorStatus,
    VMDTemperature,
)
from pyairios.data_model import AiriosNodeData
from pyairios.exceptions import AiriosException

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONF_SLAVE,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import VMDEntityFeature
from .coordinator import AiriosDataUpdateCoordinator
from .entity import AiriosEntity
from .services import SERVICE_DEVICE_RESET, SERVICE_FACTORY_RESET

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AiriosSensorEntityDescription(SensorEntityDescription):
    """Airios sensor description."""

    value_fn: Callable[[Any], StateType] | None = None
    supported_features: VMDEntityFeature | None = None


VMD_ERROR_CODE_MAP: dict[VMDErrorCode, str] = {
    VMDErrorCode.NO_ERROR: "no_error",
    VMDErrorCode.NON_SPECIFIC_FAULT: "non_specific_fault",
    VMDErrorCode.EMERGENCY_STOP: "emergency_stop",
    VMDErrorCode.FAN_1_ERROR: "fan_1_error",
    VMDErrorCode.FAN_2_ERROR: "fan_2_error",
    VMDErrorCode.X20_SENSOR_ERROR: "x20_sensor_error",
    VMDErrorCode.X21_SENSOR_ERROR: "x21_sensor_error",
    VMDErrorCode.X22_SENSOR_ERROR: "x22_sensor_error",
    VMDErrorCode.X23_SENSOR_ERROR: "x23_sensor_error",
    VMDErrorCode.BINDING_MODE_ACTIVE: "binding_mode_active",
    VMDErrorCode.IDENTIFICATION_ACTIVE: "identification_active",
}


def power_on_time_value_fn(v: timedelta) -> StateType:
    """Convert timedelta to sensor's value."""
    return v.total_seconds()


def error_code_value_fn(v: VMDErrorCode) -> StateType:
    """Convert VMDErrorCode to sensor's value."""
    return VMD_ERROR_CODE_MAP.get(v)


def temperature_value_fn(v: VMDTemperature) -> StateType:
    """Convert VMDTemperature to sensor's value."""
    if v.status == VMDSensorStatus.OK:
        return v.temperature
    return None


def bypass_position_value_fn(v: VMDBypassPosition) -> StateType:
    """Convert VMDTemperature to sensor's value."""
    if not v.error:
        return v.position
    return None


def override_remaining_time_value_fn(v: int) -> StateType:
    """Entity return not available when 0."""
    if v == 0:
        return None
    return v


def postheater_value_fn(v: VMDHeater) -> StateType:
    """Convert VMDHeater to sensor's value."""
    if v.status == VMDHeaterStatus.OK:
        return v.level
    return None


BRIDGE_SENSOR_ENTITIES: tuple[AiriosSensorEntityDescription, ...] = (
    AiriosSensorEntityDescription(
        key="rf_load_last_hour",
        translation_key="rf_load_last_hour",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    AiriosSensorEntityDescription(
        key="rf_load_current_hour",
        translation_key="rf_load_current_hour",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
    ),
    AiriosSensorEntityDescription(
        key="rf_sent_messages_last_hour",
        translation_key="rf_sent_messages_last_hour",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AiriosSensorEntityDescription(
        key="rf_sent_messages_current_hour",
        translation_key="rf_sent_messages_current_hour",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AiriosSensorEntityDescription(
        key="power_on_time",
        translation_key="power_on_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=power_on_time_value_fn,
        supported_features=VMDEntityFeature.DEVICE_RESET
        | VMDEntityFeature.FACTORY_RESET,
    ),
)

VMD_SENSOR_ENTITIES: tuple[AiriosSensorEntityDescription, ...] = (
    AiriosSensorEntityDescription(
        key="indoor_air_temperature",
        translation_key="indoor_air_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=temperature_value_fn,
    ),
    AiriosSensorEntityDescription(
        key="outdoor_air_temperature",
        translation_key="outdoor_air_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=temperature_value_fn,
    ),
    AiriosSensorEntityDescription(
        key="exhaust_air_temperature",
        translation_key="exhaust_air_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=temperature_value_fn,
    ),
    AiriosSensorEntityDescription(
        key="supply_air_temperature",
        translation_key="supply_air_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=temperature_value_fn,
    ),
    AiriosSensorEntityDescription(
        key="exhaust_fan_rpm",
        translation_key="exhaust_fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AiriosSensorEntityDescription(
        key="supply_fan_rpm",
        translation_key="supply_fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AiriosSensorEntityDescription(
        key="supply_fan_speed",
        translation_key="supply_fan_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    AiriosSensorEntityDescription(
        key="exhaust_fan_speed",
        translation_key="exhaust_fan_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    AiriosSensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(VMD_ERROR_CODE_MAP.values())),
        value_fn=error_code_value_fn,
    ),
    AiriosSensorEntityDescription(
        key="filter_duration_days",
        translation_key="filter_duration_days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AiriosSensorEntityDescription(
        key="filter_remaining_percent",
        translation_key="filter_remaining_percent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    AiriosSensorEntityDescription(
        key="bypass_position",
        translation_key="bypass_position",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=bypass_position_value_fn,
    ),
    AiriosSensorEntityDescription(
        key="postheater",
        translation_key="postheater",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=postheater_value_fn,
    ),
    AiriosSensorEntityDescription(
        key="override_remaining_time",
        translation_key="override_remaining_time",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=override_remaining_time_value_fn,
    ),
)


class AiriosSensorEntity(AiriosEntity, SensorEntity):
    """Airios sensor."""

    entity_description: AiriosSensorEntityDescription

    def __init__(
        self,
        description: AiriosSensorEntityDescription,
        coordinator: AiriosDataUpdateCoordinator,
        node: AiriosNodeData,
        via_config_entry: ConfigEntry | None,
        subentry: ConfigSubentry | None,
    ) -> None:
        """Initialize the Airios sensor entity."""
        super().__init__(description.key, coordinator, node, via_config_entry, subentry)
        self.entity_description = description
        self._attr_supported_features = description.supported_features

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update data from the coordinator."""
        _LOGGER.debug(
            "Handle update for node %s sensor %s",
            f"{self.rf_address}",
            self.entity_description.key,
        )
        try:
            device = self.coordinator.data.nodes[self.slave_id]
            result = device[self.entity_description.key]
            _LOGGER.debug(
                "Node %s, sensor %s, result %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                result,
            )
            if result is not None and result.value is not None:
                if self.entity_description.value_fn:
                    self._attr_native_value = self.entity_description.value_fn(
                        result.value
                    )
                else:
                    self._attr_native_value = result.value
                self._attr_available = self._attr_native_value is not None
                if result.status is not None:
                    self.set_extra_state_attributes_internal(result.status)

        except (TypeError, ValueError) as ex:
            _LOGGER.error(
                "Failed to update node %s sensor %s: %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                ex,
            )
            self._attr_native_value = None
            self._attr_available = False
        finally:
            self.async_write_ha_state()

    @final
    async def async_device_reset(self) -> bool:
        """Reset the bridge."""
        node = cast(BRDG02R13, await self.api().node(self.slave_id))
        _LOGGER.info("Reset node %s", str(node))
        try:
            if not await node.reset(ResetMode.SOFT_RESET):
                raise HomeAssistantError("Failed to reset device")
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to reset device: {ex}") from ex
        return True

    @final
    async def async_factory_reset(self) -> bool:
        """Reset the bridge."""
        node = cast(BRDG02R13, await self.api().node(self.slave_id))
        _LOGGER.info("Factory reset node %s", str(node))
        try:
            if not await node.reset(ResetMode.FACTORY_RESET):
                raise HomeAssistantError("Failed to factory reset device")
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to factory reset device: {ex}") from ex
        return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""

    coordinator: AiriosDataUpdateCoordinator = entry.runtime_data

    for slave_id, node in coordinator.data.nodes.items():
        # Find matching subentry
        subentry_id = None
        subentry = None
        via_config_entry = None
        for se_id, se in entry.subentries.items():
            if se.data[CONF_SLAVE] == slave_id:
                subentry_id = se_id
                subentry = se
                via_config_entry = entry

        result = node["product_id"]
        if result is None or result.value is None:
            raise ConfigEntryNotReady("Failed to fetch product id from node")

        entities: list[AiriosSensorEntity] = []
        if result.value == ProductId.BRDG_02R13:
            entities.extend(
                [
                    AiriosSensorEntity(
                        description, coordinator, node, via_config_entry, subentry
                    )
                    for description in BRIDGE_SENSOR_ENTITIES
                ]
            )
        elif result.value == ProductId.VMD_02RPS78:
            entities.extend(
                [
                    AiriosSensorEntity(
                        description, coordinator, node, via_config_entry, subentry
                    )
                    for description in VMD_SENSOR_ENTITIES
                ]
            )
        async_add_entities(entities, config_subentry_id=subentry_id)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_DEVICE_RESET,
        None,
        "async_device_reset",
        required_features=[VMDEntityFeature.DEVICE_RESET],
    )
    platform.async_register_entity_service(
        SERVICE_FACTORY_RESET,
        None,
        "async_factory_reset",
        required_features=[VMDEntityFeature.FACTORY_RESET],
    )
