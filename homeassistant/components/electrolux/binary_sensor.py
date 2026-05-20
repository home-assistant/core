"""Binary sensor entity for Electrolux Integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, TypeVar

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
    DOOR_STATE,
    DRAWER_STATUS,
    HOOD_AUTO_SWITCH_OFF_EVENT,
    UI_LOCK_MODE,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import convert_to_snake_case

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=ApplianceData)


@dataclass(frozen=True, kw_only=True)
class ElectroluxBinarySensorDescription[T = ApplianceData](
    BinarySensorEntityDescription
):
    """Custom binary sensor description for Electrolux sensors."""

    exists_fn: Callable[[T], bool] = lambda appliance: True
    value_fn: Callable[[T], Any]
    mapping: dict[Any, bool] | None = None


@dataclass(frozen=True, kw_only=True)
class ElectroluxCavityBinarySensorDescription[T = ApplianceData](
    BinarySensorEntityDescription
):
    """Custom binary sensor description for Electrolux appliance cavity sensors."""

    exists_fn: Callable[[T, str], bool] = lambda appliance, cavity: True
    value_fn: Callable[[T, str], Any]
    mapping: dict[Any, bool] | None = None


def _connection_state_value_fn(appliance: ApplianceData):
    if TYPE_CHECKING:
        assert appliance.state

    return appliance.state.connectionState


GENERAL_ELECTROLUX_SENSORS: tuple[ElectroluxBinarySensorDescription, ...] = (
    ElectroluxBinarySensorDescription(
        key="connection_state",
        translation_key="connection_state",
        icon="mdi:wifi",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_connection_state_value_fn,
        mapping={"connected": True, "disconnected": False},
    ),
)

HOB_ELECTROLUX_SENSORS: tuple[ElectroluxBinarySensorDescription[HBAppliance], ...] = (
    ElectroluxBinarySensorDescription(
        key="ui_lock_mode",
        translation_key="ui_lock_mode",
        icon="mdi:lock",
        device_class=BinarySensorDeviceClass.LOCK,
        exists_fn=lambda appliance: appliance.is_feature_supported(UI_LOCK_MODE),
        value_fn=lambda appliance: appliance.get_current_ui_lock_mode(),
        mapping={True: False, False: True},
    ),
)

HOOD_ELECTROLUX_SENSORS: tuple[ElectroluxBinarySensorDescription[HDAppliance], ...] = (
    ElectroluxBinarySensorDescription(
        key="drawer_status",
        translation_key="drawer_status",
        icon="mdi:file-cabinet",
        exists_fn=lambda appliance: appliance.is_feature_supported(DRAWER_STATUS),
        value_fn=lambda appliance: appliance.get_current_drawer_status(),
    ),
    ElectroluxBinarySensorDescription(
        key="hood_auto_switch_off_event",
        translation_key="hood_auto_switch_off_event",
        icon="mdi:power-sleep",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            HOOD_AUTO_SWITCH_OFF_EVENT
        ),
        value_fn=lambda appliance: appliance.get_current_hood_auto_switch_off_event(),
    ),
)

CARE_ELECTROLUX_SENSORS: tuple[
    ElectroluxBinarySensorDescription[
        DWAppliance | TDAppliance | WDAppliance | WMAppliance
    ],
    ...,
] = (
    ElectroluxBinarySensorDescription(
        key="door_state",
        translation_key="door_state",
        icon="mdi:door",
        device_class=BinarySensorDeviceClass.DOOR,
        exists_fn=lambda appliance: appliance.is_feature_supported(DOOR_STATE),
        value_fn=lambda appliance: appliance.get_current_door_state(),
        mapping={"closed": False, "open": True},
    ),
    ElectroluxBinarySensorDescription(
        key="ui_lock_mode",
        translation_key="ui_lock_mode",
        icon="mdi:lock",
        device_class=BinarySensorDeviceClass.LOCK,
        exists_fn=lambda appliance: appliance.is_feature_supported(UI_LOCK_MODE),
        value_fn=lambda appliance: appliance.get_current_ui_lock_mode(),
        mapping={True: False, False: True},
    ),
)

REFRIGERATOR_GENERIC_ELECTROLUX_SENSORS: tuple[
    ElectroluxBinarySensorDescription[CRAppliance], ...
] = (
    ElectroluxBinarySensorDescription(
        key="ui_lock_mode",
        translation_key="ui_lock_mode",
        icon="mdi:lock",
        device_class=BinarySensorDeviceClass.LOCK,
        exists_fn=lambda appliance: appliance.is_feature_supported(UI_LOCK_MODE),
        value_fn=lambda appliance: appliance.get_current_ui_lock_mode(),
        mapping={True: False, False: True},
    ),
)

OVEN_ELECTROLUX_SENSORS: tuple[ElectroluxBinarySensorDescription[OVAppliance], ...] = (
    ElectroluxBinarySensorDescription(
        key="door_state",
        translation_key="door_state",
        icon="mdi:door",
        device_class=BinarySensorDeviceClass.DOOR,
        exists_fn=lambda appliance: appliance.is_feature_supported(DOOR_STATE),
        value_fn=lambda appliance: appliance.get_current_door_state(),
        mapping={"closed": False, "open": True},
    ),
)

STRUCTURED_OVEN_CAVITY_ELECTROLUX_SENSORS: tuple[
    ElectroluxCavityBinarySensorDescription[SOAppliance], ...
] = (
    ElectroluxCavityBinarySensorDescription[SOAppliance](
        key="door_state",
        translation_key="door_state",
        icon="mdi:door",
        device_class=BinarySensorDeviceClass.DOOR,
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, DOOR_STATE
        ),
        value_fn=lambda appliance, cavity: appliance.get_current_cavity_door_state(
            cavity
        ),
        mapping={"closed": False, "open": True},
    ),
)

FREEZER_FRIDGE_ICE_MAKER_EXTRA_CAVITY_ELECTROLUX_SENSORS: tuple[
    ElectroluxCavityBinarySensorDescription[CRAppliance], ...
] = (
    ElectroluxCavityBinarySensorDescription(
        key="door_state",
        translation_key="door_state",
        icon="mdi:door",
        device_class=BinarySensorDeviceClass.DOOR,
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, DOOR_STATE
        ),
        value_fn=lambda appliance, cavity: appliance.get_current_cavity_door_state(
            cavity
        ),
        mapping={"closed": False, "open": True},
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
            ACAppliance,
            APAppliance,
            CRAppliance,
            DAMACAppliance,
            DHAppliance,
            DWAppliance,
            HBAppliance,
            HDAppliance,
            OVAppliance,
            RVCAppliance,
            SOAppliance,
            TDAppliance,
            WDAppliance,
            WMAppliance,
        ),
    ):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in GENERAL_ELECTROLUX_SENSORS
        )

    if isinstance(appliance_data, HBAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in HOB_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, HDAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in HOOD_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, (DWAppliance, TDAppliance, WDAppliance, WMAppliance)):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in CARE_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, OVAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in OVEN_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, SOAppliance):
        entities.extend(
            ElectroluxCavitySensor(appliance_data, coordinator, cavity, description)
            for description in STRUCTURED_OVEN_CAVITY_ELECTROLUX_SENSORS
            for cavity in appliance_data.get_supported_cavities()
            if description.exists_fn(appliance_data, cavity)
        )

    if isinstance(appliance_data, CRAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in REFRIGERATOR_GENERIC_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

        entities.extend(
            ElectroluxCavitySensor(appliance_data, coordinator, cavity, description)
            for description in FREEZER_FRIDGE_ICE_MAKER_EXTRA_CAVITY_ELECTROLUX_SENSORS
            for cavity in appliance_data.get_supported_cavities()
            if description.exists_fn(appliance_data, cavity)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set binary sensor for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxSensor(ElectroluxBaseEntity[T], BinarySensorEntity):
    """Representation of a generic binary sensor for Electrolux appliances."""

    entity_description: ElectroluxBinarySensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxBinarySensorDescription[T],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(appliance_data, coordinator, description.key)
        self.entity_description = description

    def _update_attr_state(self) -> bool:
        new_value = self._get_value()
        if self._attr_is_on != new_value:
            self._attr_is_on = new_value
            return True
        return False

    def _get_value(self) -> bool | None:
        description = self.entity_description
        entity_key = description.key
        value = description.value_fn(self._appliance_data)
        if isinstance(value, str):
            value = convert_to_snake_case(value)

        if description.mapping is not None:
            return _map_to_known_value(description.mapping, entity_key, value)

        if not isinstance(value, bool):
            _LOGGER.warning(
                "A non-bool value was detected for a binary sensor of the Electrolux integration. "
                "Please report it for the integration, and include the following information: "
                'entity key="%s", reported value="%s"',
                entity_key,
                value,
            )
            return None
        return value


class ElectroluxCavitySensor(ElectroluxBaseEntity[T], BinarySensorEntity):
    """Representation of a generic binary sensor for appliance cavities."""

    entity_description: ElectroluxCavityBinarySensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        cavity: str,
        description: ElectroluxCavityBinarySensorDescription[T],
    ) -> None:
        """Initialize the sensor."""
        entity_key = f"{convert_to_snake_case(cavity)}_{description.key}"
        super().__init__(appliance_data, coordinator, entity_key)

        self._cavity = cavity
        self.entity_description = description
        self._attr_translation_key = entity_key

    def _update_attr_state(self) -> bool:
        new_value = self._get_value()
        if self._attr_is_on != new_value:
            self._attr_is_on = new_value
            return True
        return False

    def _get_value(self) -> Any:
        description = self.entity_description
        entity_key = f"{convert_to_snake_case(self._cavity)}_{description.key}"
        value = description.value_fn(self._appliance_data, self._cavity)
        if isinstance(value, str):
            value = convert_to_snake_case(value)

        if description.mapping is not None:
            return _map_to_known_value(description.mapping, entity_key, value)

        if not isinstance(value, bool):
            _LOGGER.warning(
                "A non-bool value was detected for a binary sensor of the Electrolux integration. "
                "Please report it for the integration, and include the following information: "
                'entity key="%s", reported value="%s"',
                entity_key,
                value,
            )
            return None
        return value


_valid_type = str | float | int


def _map_to_known_value(
    mapping: dict[_valid_type, bool], entity_key: str, value: _valid_type
) -> bool | None:
    """Map to boolean based on mapping; log warn message if value is not found in mapping."""
    if value not in mapping:
        _LOGGER.warning(
            "An unknown value %s was reported for a binary sensor of the Electrolux integration. "
            "Please report it for the integration, and include the following information: "
            'entity key="%s", reported value="%s"',
            value,
            entity_key,
            value,
        )
    return mapping.get(value)
