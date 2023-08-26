"""Data constants for the ScreenLogic integration."""
from collections.abc import Callable, Generator
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any

from screenlogicpy import ScreenLogicGateway
from screenlogicpy.const.data import ATTR, DEVICE, VALUE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN as SL_DOMAIN, SL_UNIT_TO_HA_UNIT, ScreenLogicDataPath
from .coordinator import ScreenlogicDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class PathPart(StrEnum):
    """Placeholders for local data_path values."""

    DEVICE = "!device"
    KEY = "!key"
    INDEX = "!index"
    VALUE = "!sensor"


ScreenLogicDataPathTemplate = tuple[PathPart | str | int, ...]


class ScreenLogicRule:
    """Represents a base default passing rule."""

    def __init__(
        self, test: Callable[..., bool] = lambda gateway, data_path: True
    ) -> None:
        """Initialize a ScreenLogic rule."""
        self._test = test

    def test(self, gateway: ScreenLogicGateway, data_path: ScreenLogicDataPath) -> bool:
        """Method to check the rule."""
        return self._test(gateway, data_path)


class ScreenLogicDataRule(ScreenLogicRule):
    """Represents a data rule."""

    def __init__(
        self, test: Callable[..., bool], test_path_template: tuple[PathPart, ...]
    ) -> None:
        """Initialize a ScreenLogic data rule."""
        self._test_path_template = test_path_template
        super().__init__(test)

    def test(self, gateway: ScreenLogicGateway, data_path: ScreenLogicDataPath) -> bool:
        """Check the rule against the gateway's data."""
        test_path = realize_path_template(self._test_path_template, data_path)
        return self._test(gateway.get_data(*test_path))


class ScreenLogicEquipmentRule(ScreenLogicRule):
    """Represents an equipment flag rule."""

    def test(self, gateway: ScreenLogicGateway, data_path: ScreenLogicDataPath) -> bool:
        """Check the rule against the gateway's equipment flags."""
        return self._test(gateway.equipment_flags)


@dataclass
class SupportedValueParameters:
    """Base supported values for ScreenLogic Entities."""

    enabled: ScreenLogicRule = ScreenLogicRule()
    included: ScreenLogicRule = ScreenLogicRule()
    subscription_code: int | None = None


SupportedValueDescriptions = dict[str, SupportedValueParameters]

SupportedGroupDescriptions = dict[int | str, SupportedValueDescriptions]

SupportedDeviceDescriptions = dict[str, SupportedGroupDescriptions]


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


# not run-time
def get_ha_unit(entity_data: dict) -> StrEnum | str | None:
    """Return a Home Assistant unit of measurement from a UNIT."""
    sl_unit = entity_data.get(ATTR.UNIT)
    return SL_UNIT_TO_HA_UNIT.get(sl_unit, sl_unit)


# partial run-time
def realize_path_template(
    template_path: ScreenLogicDataPathTemplate, data_path: ScreenLogicDataPath
) -> tuple[str | int, ...]:
    """Make data path from template and current."""
    if not data_path or len(data_path) < 3:
        raise KeyError(
            f"Missing or invalid required parameter: 'data_path' for template path '{template_path}'"
        )
    device, group, data_key = data_path
    realized_path: list[str | int] = []
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


def cleanup_excluded_entity(
    coordinator: ScreenlogicDataUpdateCoordinator,
    platform_domain: str,
    entity_key: str,
) -> None:
    """Remove excluded entity if it exists."""
    assert coordinator.config_entry
    entity_registry = er.async_get(coordinator.hass)
    unique_id = f"{coordinator.config_entry.unique_id}_{entity_key}"
    if entity_id := entity_registry.async_get_entity_id(
        platform_domain, SL_DOMAIN, unique_id
    ):
        _LOGGER.debug(
            "Removing existing entity '%s' per data inclusion rule", entity_id
        )
        entity_registry.async_remove(entity_id)


def preprocess_supported_values(
    supported_devices: SupportedDeviceDescriptions,
) -> list[tuple[ScreenLogicDataPath, Any]]:
    """Expand config dict into list of ScreenLogicDataPaths and settings."""
    processed: list[tuple[ScreenLogicDataPath, Any]] = []
    for device, device_groups in supported_devices.items():
        for group, group_values in device_groups.items():
            for value_key, value_params in group_values.items():
                value_data_path = (device, group, value_key)
                processed.append((value_data_path, value_params))
    return processed


def iterate_expand_group_wildcard(
    gateway: ScreenLogicGateway,
    preprocessed_data: list[tuple[ScreenLogicDataPath, Any]],
) -> Generator[tuple[ScreenLogicDataPath, Any], None, None]:
    """Iterate and expand any group wildcards to all available entries in gateway."""
    for data_path, value_params in preprocessed_data:
        device, group, value_key = data_path
        if group == "*":
            for index in gateway.get_data(device):
                yield ((device, index, value_key), value_params)
        else:
            yield (data_path, value_params)


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
