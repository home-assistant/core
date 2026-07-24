"""Home Assistant mappings for Beatbot product categories."""

from beatbot_cloud import DeviceStatus, ProductCategory, error_mask_for, status_for

from homeassistant.components.vacuum import VacuumActivity, VacuumEntityFeature

from ..models import BeatbotCapability
from .const import (
    INTERFACE_PAUSE,
    INTERFACE_RETURN_TO_BASE,
    INTERFACE_START,
    INTERFACE_VACUUM_STATE,
)

CATEGORY_MAP: dict[str, ProductCategory] = {
    category.value: category for category in ProductCategory
}

VACUUM_ACTIVITY_BY_STATUS: dict[DeviceStatus, VacuumActivity] = {
    DeviceStatus.STANDBY: VacuumActivity.IDLE,
    DeviceStatus.GOTO_CHARGE: VacuumActivity.RETURNING,
    DeviceStatus.CHARGING: VacuumActivity.DOCKED,
    DeviceStatus.CHARGE_DONE: VacuumActivity.DOCKED,
    DeviceStatus.PAUSED: VacuumActivity.PAUSED,
    DeviceStatus.CLEANING: VacuumActivity.CLEANING,
    DeviceStatus.SLEEP: VacuumActivity.IDLE,
    DeviceStatus.RETURN_TRIP: VacuumActivity.RETURNING,
    DeviceStatus.CLEAN_DONE: VacuumActivity.IDLE,
    DeviceStatus.REMOTE_CONTROL: VacuumActivity.CLEANING,
    DeviceStatus.CLEAN_WAIT: VacuumActivity.IDLE,
    DeviceStatus.WIFI_CONNECT: VacuumActivity.IDLE,
    DeviceStatus.DIVING: VacuumActivity.CLEANING,
    DeviceStatus.EMERGE: VacuumActivity.CLEANING,
    DeviceStatus.AUTO_DOCK: VacuumActivity.RETURNING,
    DeviceStatus.FINISH_CONNECT: VacuumActivity.RETURNING,
    DeviceStatus.DOCK: VacuumActivity.DOCKED,
    DeviceStatus.SELF_CLEANING: VacuumActivity.CLEANING,
    DeviceStatus.REPLENISH_ENERGY: VacuumActivity.IDLE,
    DeviceStatus.CHASE_LIGHT: VacuumActivity.CLEANING,
    DeviceStatus.DOCK_DONE: VacuumActivity.DOCKED,
    DeviceStatus.UNCHECK: VacuumActivity.IDLE,
    DeviceStatus.SELF_CHECKING: VacuumActivity.PAUSED,
    DeviceStatus.CHECK_DOWN: VacuumActivity.PAUSED,
}

VACUUM_FEATURES_BY_CATEGORY: dict[ProductCategory, VacuumEntityFeature] = dict.fromkeys(
    ProductCategory, VacuumEntityFeature.STATE
)


def vacuum_activity(
    category: ProductCategory, work_status: int, error_code: int
) -> VacuumActivity:
    """Return the Home Assistant activity for a Beatbot device state."""
    include_notices = category is not ProductCategory.CLEAN_BASE_STATION
    if error_code & error_mask_for(category, include_notices=include_notices):
        return VacuumActivity.ERROR
    if status := status_for(category, work_status):
        return VACUUM_ACTIVITY_BY_STATUS[status]
    return VacuumActivity.IDLE


def vacuum_features_from_capabilities(
    capabilities: dict[str, BeatbotCapability],
) -> VacuumEntityFeature | None:
    """Derive vacuum features from the device's advertised capabilities."""
    if not capabilities:
        return None

    vacuum_capability_keys = {
        INTERFACE_VACUUM_STATE,
        INTERFACE_START,
        INTERFACE_PAUSE,
        INTERFACE_RETURN_TO_BASE,
    }
    if not (vacuum_capability_keys & capabilities.keys()):
        return None

    features = VacuumEntityFeature(0)
    state = capabilities.get(INTERFACE_VACUUM_STATE)
    if state is not None and state.retrievable:
        features |= VacuumEntityFeature.STATE
    start = capabilities.get(INTERFACE_START)
    if start is not None and not start.non_controllable:
        features |= VacuumEntityFeature.START
    pause = capabilities.get(INTERFACE_PAUSE)
    if pause is not None and not pause.non_controllable:
        features |= VacuumEntityFeature.PAUSE
    return_to_base = capabilities.get(INTERFACE_RETURN_TO_BASE)
    if return_to_base is not None and not return_to_base.non_controllable:
        features |= VacuumEntityFeature.RETURN_HOME
    return features
