"""Const for TP-Link."""
import datetime

DOMAIN = "tplink"
ATTR_CONFIG = "config"
CONF_DIMMER = "dimmer"
CONF_DISCOVERY = "discovery"
CONF_LIGHT = "light"
CONF_RETRY_DELAY = "retry_delay"
CONF_RETRY_MAX_ATTEMPTS = "retry_max_attempts"
CONF_STRIP = "strip"
CONF_SWITCH = "switch"
DEFAULT_MAX_ATTEMPTS = 300
DEFAULT_RETRY_DELAY = 2
DEFAULT_DISCOVERY = True
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=8)
