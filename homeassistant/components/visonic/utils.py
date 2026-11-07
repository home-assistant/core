"""Simple Utility Functions."""

from collections.abc import Iterable
from datetime import datetime

from homeassistant.util import dt as dt_util

from .const import VISONIC_ALARM
from .visonic_types import AlarmPanelStatus

_PARTITION_STATUS_PRIORITY = {
    status: priority
    for priority, status in enumerate(
        (
            AlarmPanelStatus.UNKNOWN,
            AlarmPanelStatus.DISARMED,
            AlarmPanelStatus.ARMING_HOME,
            AlarmPanelStatus.ARMING_AWAY,
            AlarmPanelStatus.ARMED_HOME,
            AlarmPanelStatus.ARMED_AWAY,
            AlarmPanelStatus.ARMED_HOME_BYPASS,
            AlarmPanelStatus.ARMED_AWAY_BYPASS,
            AlarmPanelStatus.ARMED_HOME_INSTANT,
            AlarmPanelStatus.ARMED_AWAY_INSTANT,
            AlarmPanelStatus.ENTRY_DELAY,
            AlarmPanelStatus.ENTRY_DELAY_INSTANT,
            AlarmPanelStatus.USER_TEST,
            AlarmPanelStatus.DOWNLOADING,
            AlarmPanelStatus.INSTALLER,
            AlarmPanelStatus.TRIGGERED,
        )
    )
}


def combine_partition_statuses(
    statuses: Iterable[AlarmPanelStatus],
) -> AlarmPanelStatus:
    """Combine partitions without hiding entry delays behind steady armed states."""
    return max(
        statuses,
        key=_PARTITION_STATUS_PRIORITY.__getitem__,
        default=AlarmPanelStatus.UNKNOWN,
    )


###################################################################################
#################  General Utility Functions ######################################
###################################################################################


# get the current date and time - UTC
def get_utc_time() -> datetime:
    """Return the current UTC time."""
    return dt_util.utcnow()


def capitalize(s: str) -> str:
    """Capitalize the first letter of a string and lowercase the rest."""
    return s[:1].upper() + s[1:].lower() if s else ""


def to_bool(val: bool | int | str | None) -> bool:
    """Convert value to boolean."""
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val != 0
    if isinstance(val, str):
        v = val.lower()
        return v not in ["no", "false", "0"]
    return False


def get_alarm_panel_unique_ident(panel_ident: int | str) -> str:
    """Get alarm panel unique ident."""
    if isinstance(panel_ident, str):
        return f"{VISONIC_ALARM} {panel_ident}"
    if panel_ident > 0:
        return VISONIC_ALARM + " P" + str(panel_ident)
    return VISONIC_ALARM
