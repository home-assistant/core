"""Data constants for the ScreenLogic integration."""
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import logging

from screenlogicpy import ScreenLogicGateway
from screenlogicpy.const.data import ATTR, DEVICE, VALUE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN as SL_DOMAIN, SL_UNIT_TO_HA_UNIT, generate_unique_id
from .coordinator import ScreenlogicDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class EntityParameter(StrEnum):
    """Parameters for sensor mapping."""

    ENABLED = "enabled"  # ScreenLogicRule
    ENTITY_CATEGORY = "entity_category"  # EntityCategory
    INCLUDED = "included"  # ScreenLogicRule
    SET_VALUE = "set_value"  # tuple
    SUBSCRIPTION_CODE = "sub_code"  # int
    VALUE_MODIFICATION = "value_mod"  # Callable


class PathPart(StrEnum):
    """Placeholders for local data_path values."""

    DEVICE = "!device"
    KEY = "!key"
    INDEX = "!index"
    VALUE = "!sensor"


class ScreenLogicRule(ABC):
    """Base class for checking rules against a ScreenlogicGateway."""

    def __init__(self, test: Callable[..., bool]) -> None:
        """Initialize a ScreenLogic rule."""
        self._test = test

    @abstractmethod
    def test(
        self, gateway: ScreenLogicGateway, data_path: tuple[str | int, ...]
    ) -> bool:
        """Abstract method to check the rule."""


class ScreenLogicDataRule(ScreenLogicRule):
    """Represents a data rule."""

    def __init__(
        self, test: Callable[..., bool], test_path_template: tuple[str | int, ...]
    ) -> None:
        """Initialize a ScreenLogic data rule."""
        self._test_path_template = test_path_template
        super().__init__(test)

    def test(
        self, gateway: ScreenLogicGateway, data_path: tuple[str | int, ...]
    ) -> bool:
        """Check the rule against the gateway's data."""
        test_path = realize_path_template(self._test_path_template, data_path)
        return self._test(gateway.get_data(*test_path))


class ScreenLogicEquipmentRule(ScreenLogicRule):
    """Represents an equipment flag rule."""

    def test(
        self, gateway: ScreenLogicGateway, data_path: tuple[str | int, ...]
    ) -> bool:
        """Check the rule against the gateway's equipment flags."""
        return self._test(gateway.equipment_flags)


SupportedValueParameters = dict[
    EntityParameter,
    Callable | EntityCategory | int | ScreenLogicRule | tuple,
]

SupportedValueDescriptions = dict[str, SupportedValueParameters | dict]

SupportedGroupDescriptions = dict[int | str, SupportedValueDescriptions]

SupportedDeviceDescriptions = dict[str, SupportedGroupDescriptions]


@dataclass
class BaseScreenLogicEntityData:
    """Generic representation of a ScreenLogic entity."""

    data_path: tuple[str | int, ...]
    enabled: bool
    entity_key: str
    subscription_code: int | None
    value_data: dict
    value_parameters: dict


DEVICE_INCLUSION_RULES = {
    DEVICE.PUMP: ScreenLogicDataRule(
        lambda pump_data: pump_data[VALUE.DATA] != 0,
        (PathPart.DEVICE, PathPart.INDEX),
    ),
    DEVICE.INTELLICHEM: ScreenLogicEquipmentRule(
        lambda flags: EQUIPMENT_FLAG.INTELLICHEM in flags,
    ),
    DEVICE.SCG: ScreenLogicEquipmentRule(
        lambda flags: EQUIPMENT_FLAG.CHLORINATOR in flags,
    ),
}

DEVICE_SUBSCRIPTION = {
    DEVICE.CONTROLLER: CODE.STATUS_CHANGED,
    DEVICE.INTELLICHEM: CODE.CHEMISTRY_CHANGED,
}


def get_ha_unit(entity_data: dict) -> StrEnum | str | None:
    """Return a Home Assistant unit of measurement from a UNIT."""
    sl_unit = entity_data.get(ATTR.UNIT)
    return SL_UNIT_TO_HA_UNIT.get(sl_unit, sl_unit)


def realize_path_template(
    template_path: tuple[str | int, ...], data_path: tuple[str | int, ...]
) -> tuple[str | int, ...]:
    """Make data path from template and current."""
    if not data_path or len(data_path) < 3:
        raise KeyError(
            f"Missing or invalid required parameter: 'data_path' for template path '{template_path}'"
        )
    device, group, data_key = data_path
    realized_path = []
    for part in template_path:
        match part:
            case PathPart.DEVICE:
                realized_path.append(device)
            case PathPart.INDEX | PathPart.KEY:
                realized_path.append(group)
            case PathPart.VALUE:
                realized_path.append(data_key)
            case _:
                realized_path.append(part)

    return tuple(realized_path)


def process_supported_values(
    coordinator: ScreenlogicDataUpdateCoordinator,
    platform_domain: str,
    supported_devices: SupportedDeviceDescriptions,
):
    """Process template data."""
    entity_registry = er.async_get(coordinator.hass)

    def cleanup_excluded_entity(entity_key: str):
        """Remove entity if it exists."""
        assert coordinator.config_entry
        unique_id = f"{coordinator.config_entry.unique_id}_{entity_key}"
        if entity_id := entity_registry.async_get_entity_id(
            platform_domain, SL_DOMAIN, unique_id
        ):
            _LOGGER.debug(
                f"Removing existing entity '{entity_id}' per data inclusion rule"
            )
            entity_registry.async_remove(entity_id)

    gateway = coordinator.gateway

    for device, device_groups in supported_devices.items():
        if "*" in device_groups:
            indexed_values = device_groups.pop("*")
            for index in gateway.get_data(device):
                device_groups[index] = indexed_values
        for group, group_values in device_groups.items():
            for value_key, value_params in group_values.items():
                data_path = (device, group, value_key)

                entity_key = generate_unique_id(device, group, value_key)

                if (
                    inclusion_rule := value_params.get(EntityParameter.INCLUDED)
                    or DEVICE_INCLUSION_RULES.get(device)
                ) is not None:
                    assert isinstance(inclusion_rule, ScreenLogicRule)
                    if not inclusion_rule.test(gateway, data_path):
                        cleanup_excluded_entity(entity_key)
                        continue

                try:
                    value_data = gateway.get_data(*data_path, strict=True)
                except KeyError:
                    _LOGGER.debug(f"Failed to find {data_path}")
                    continue

                sub_code = value_params.get(
                    EntityParameter.SUBSCRIPTION_CODE
                ) or DEVICE_SUBSCRIPTION.get(device)
                assert sub_code is None or isinstance(sub_code, int)

                enabled = True
                if (
                    enabled_rule := value_params.get(EntityParameter.ENABLED)
                ) is not None:
                    assert isinstance(enabled_rule, ScreenLogicRule)
                    enabled = enabled_rule.test(gateway, data_path)

                base_kwargs = {
                    "data_path": data_path,
                    "key": entity_key,
                    "entity_category": value_params.get(
                        EntityParameter.ENTITY_CATEGORY, EntityCategory.DIAGNOSTIC
                    ),
                    "entity_registry_enabled_default": enabled,
                    "name": value_data.get(ATTR.NAME),
                }

                yield base_kwargs, BaseScreenLogicEntityData(
                    data_path, enabled, entity_key, sub_code, value_data, value_params
                )


ENTITY_MIGRATIONS = {
    "chem_alarm": {
        "new_key": VALUE.ACTIVE_ALERT,
        "old_name": "Chemistry Alarm",
        "new_name": "Active Alert",
    },
    "chem_calcium_harness": {
        "new_key": VALUE.CALCIUM_HARNESS,
    },
    "chem_current_orp": {
        "new_key": VALUE.ORP_NOW,
        "old_name": "Current ORP",
        "new_name": "ORP Now",
    },
    "chem_current_ph": {
        "new_key": VALUE.PH_NOW,
        "old_name": "Current pH",
        "new_name": "pH Now",
    },
    "chem_cya": {
        "new_key": VALUE.CYA,
    },
    "chem_orp_dosing_state": {
        "new_key": VALUE.ORP_DOSING_STATE,
    },
    "chem_orp_last_dose_time": {
        "new_key": VALUE.ORP_LAST_DOSE_TIME,
    },
    "chem_orp_last_dose_volume": {
        "new_key": VALUE.ORP_LAST_DOSE_VOLUME,
    },
    "chem_orp_setpoint": {
        "new_key": VALUE.ORP_SETPOINT,
    },
    "chem_orp_supply_level": {
        "new_key": VALUE.ORP_SUPPLY_LEVEL,
    },
    "chem_ph_dosing_state": {
        "new_key": VALUE.PH_DOSING_STATE,
    },
    "chem_ph_last_dose_time": {
        "new_key": VALUE.PH_LAST_DOSE_TIME,
    },
    "chem_ph_last_dose_volume": {
        "new_key": VALUE.PH_LAST_DOSE_VOLUME,
    },
    "chem_ph_probe_water_temp": {
        "new_key": VALUE.PH_PROBE_WATER_TEMP,
    },
    "chem_ph_setpoint": {
        "new_key": VALUE.PH_SETPOINT,
    },
    "chem_ph_supply_level": {
        "new_key": VALUE.PH_SUPPLY_LEVEL,
    },
    "chem_salt_tds_ppm": {
        "new_key": VALUE.SALT_TDS_PPM,
    },
    "chem_total_alkalinity": {
        "new_key": VALUE.TOTAL_ALKALINITY,
    },
    "currentGPM": {
        "new_key": VALUE.GPM_NOW,
        "old_name": "Current GPM",
        "new_name": "GPM Now",
        "device": DEVICE.PUMP,
    },
    "currentRPM": {
        "new_key": VALUE.RPM_NOW,
        "old_name": "Current RPM",
        "new_name": "RPM Now",
        "device": DEVICE.PUMP,
    },
    "currentWatts": {
        "new_key": VALUE.WATTS_NOW,
        "old_name": "Current Watts",
        "new_name": "Watts Now",
        "device": DEVICE.PUMP,
    },
    "orp_alarm": {
        "new_key": VALUE.ORP_LOW_ALARM,
        "old_name": "ORP Alarm",
        "new_name": "ORP LOW Alarm",
    },
    "ph_alarm": {
        "new_key": VALUE.PH_HIGH_ALARM,
        "old_name": "pH Alarm",
        "new_name": "pH HIGH Alarm",
    },
    "scg_status": {
        "new_key": VALUE.STATE,
        "old_name": "SCG Status",
        "new_name": "Chlorinator",
        "device": DEVICE.SCG,
    },
    "scg_level1": {
        "new_key": VALUE.POOL_SETPOINT,
        "old_name": "Pool SCG Level",
        "new_name": "Pool Chlorinator Setpoint",
    },
    "scg_level2": {
        "new_key": VALUE.SPA_SETPOINT,
        "old_name": "Spa SCG Level",
        "new_name": "Spa Chlorinator Setpoint",
    },
    "scg_salt_ppm": {
        "new_key": VALUE.SALT_PPM,
        "old_name": "SCG Salt",
        "new_name": "Chlorinator Salt",
        "device": DEVICE.SCG,
    },
    "scg_super_chlor_timer": {
        "new_key": VALUE.SUPER_CHLOR_TIMER,
        "old_name": "SCG Super Chlorination Timer",
        "new_name": "Super Chlorination Timer",
    },
}
