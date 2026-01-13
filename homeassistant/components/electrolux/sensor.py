"""Sensor entity for Electrolux Integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

from electrolux_group_developer_sdk.client.appliances.ac_appliance import ACAppliance
from electrolux_group_developer_sdk.client.appliances.ap_appliance import APAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.dam_ac_appliance import (
    DAMACAppliance,
)
from electrolux_group_developer_sdk.client.appliances.dh_appliance import DHAppliance
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.hb_appliance import HBAppliance
from electrolux_group_developer_sdk.client.appliances.hd_appliance import HDAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.rvc_appliance import RVCAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance
from electrolux_group_developer_sdk.feature_constants import (
    APPLIANCE_STATE,
    DISPLAY_FOOD_PROBE_TEMPERATURE_C,
    DISPLAY_FOOD_PROBE_TEMPERATURE_F,
    DISPLAY_TEMPERATURE_C,
    DISPLAY_TEMPERATURE_F,
    DOOR_STATE,
    FOOD_PROBE_STATE,
    REMOTE_CONTROL,
    RUNNING_TIME,
    START_TIME,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElectroluxConfigEntry
from .coordinator import ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)

ELECTROLUX_TO_HA_TEMPERATURE_UNIT = {
    "CELSIUS": UnitOfTemperature.CELSIUS,
    "FAHRENHEIT": UnitOfTemperature.FAHRENHEIT,
}


@dataclass(frozen=True, kw_only=True)
class ElectroluxSensorDescription(SensorEntityDescription):
    """Custom sensor description for Electrolux sensors."""

    value_fn: Callable[..., Any]
    is_supported_fn: Callable[..., Any] = lambda *args: None


GENERAL_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="connection_state",
        translation_key="connection_state",
        icon="mdi:wifi",
        value_fn=lambda appliance: appliance.state.connectionState,
    ),
)

OVEN_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="start_at",
        translation_key="start_at",
        icon="mdi:timer-play-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda appliance: appliance.get_current_start_at(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(START_TIME),
    ),
    ElectroluxSensorDescription(
        key="running_time",
        translation_key="running_time",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class="measurement",
        value_fn=lambda appliance: appliance.get_current_running_time(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(RUNNING_TIME),
    ),
    ElectroluxSensorDescription(
        key="appliance_state",
        translation_key="appliance_state",
        icon="mdi:information-outline",
        value_fn=lambda appliance: appliance.get_current_appliance_state(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            APPLIANCE_STATE
        ),
    ),
    ElectroluxSensorDescription(
        key="food_probe_state",
        translation_key="food_probe_state",
        icon="mdi:thermometer-probe",
        value_fn=lambda appliance: appliance.get_current_food_probe_insertion_state(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            FOOD_PROBE_STATE
        ),
    ),
    ElectroluxSensorDescription(
        key="door_state",
        translation_key="door_state",
        icon="mdi:door",
        value_fn=lambda appliance: appliance.get_current_door_state(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(DOOR_STATE),
    ),
    ElectroluxSensorDescription(
        key="remote_control",
        translation_key="remote_control",
        icon="mdi:remote",
        value_fn=lambda appliance: appliance.get_current_remote_control(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            REMOTE_CONTROL
        ),
    ),
)

OVEN_TEMPERATURE_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="food_probe_temperature",
        translation_key="food_probe_temperature",
        icon="mdi:thermometer-probe",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class="measurement",
        value_fn=lambda appliance: appliance.get_current_display_food_probe_temperature_f()
        if appliance.get_current_temperature_unit() == "FAHRENHEIT"
        else appliance.get_current_display_food_probe_temperature_c(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_FOOD_PROBE_TEMPERATURE_F, DISPLAY_FOOD_PROBE_TEMPERATURE_C]
        ),
    ),
    ElectroluxSensorDescription(
        key="display_temperature",
        translation_key="display_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class="measurement",
        value_fn=lambda appliance: appliance.get_current_display_temperature_f()
        if appliance.get_current_temperature_unit() == "FAHRENHEIT"
        else appliance.get_current_display_temperature_c(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_TEMPERATURE_C, DISPLAY_TEMPERATURE_F]
        ),
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(
        appliance_data,
        (
            APAppliance,
            RVCAppliance,
            WMAppliance,
            WDAppliance,
            TDAppliance,
            DWAppliance,
            OVAppliance,
            HDAppliance,
            HBAppliance,
            CRAppliance,
            DHAppliance,
            ACAppliance,
            SOAppliance,
            DAMACAppliance,
        ),
    ):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in GENERAL_ELECTROLUX_SENSORS
        )

    if isinstance(appliance_data, OVAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in OVEN_ELECTROLUX_SENSORS
            if description.is_supported_fn(appliance_data)
        )

        entities.extend(
            ElectroluxTemperatureSensor(appliance_data, coordinator, description)
            for description in OVEN_TEMPERATURE_ELECTROLUX_SENSORS
            if description.is_supported_fn(appliance_data)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set sensor for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxSensor(ElectroluxBaseEntity[ApplianceData], SensorEntity):
    """Representation of a generic sensor for Electrolux appliances."""

    entity_description: ElectroluxSensorDescription

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_{description.key}"
        )
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        self._attr_native_value = self._get_value()

    def _get_value(self) -> Any:
        return self.entity_description.value_fn(self._appliance_data)


class ElectroluxTemperatureSensor(ElectroluxSensor):
    """Representation of a temperature sensor for Electrolux appliances."""

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator, description)
        self._appliance = cast(OVAppliance | CRAppliance, appliance_data)
        self._update_attr_state()

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Property for getting the current unit of measurement used by the appliance."""
        return ELECTROLUX_TO_HA_TEMPERATURE_UNIT.get(
            self._appliance.get_current_temperature_unit(), UnitOfTemperature.CELSIUS
        )

    def _update_attr_state(self) -> None:
        self._attr_native_value = self._get_value()

    def _get_value(self) -> Any:
        return self.entity_description.value_fn(self._appliance_data)
