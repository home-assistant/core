"""Support for ZoneMinder."""

from zoneminder.monitor import MonitorState

DOMAIN = "zoneminder"

CONF_INCLUDE_ARCHIVED = "include_archived"
CONF_PATH_ZMS = "path_zms"

MONITOR_FUNCTIONS = {state.value.lower(): state for state in MonitorState}

DEFAULT_COMMAND_OFF = MonitorState.MONITOR.value.lower()
DEFAULT_COMMAND_ON = MonitorState.MODECT.value.lower()
DEFAULT_INCLUDE_ARCHIVED = False
DEFAULT_PATH = "/zm/"
DEFAULT_PATH_ZMS = "/zm/cgi-bin/nph-zms"
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
