"""Constants for nmap platform."""

from __future__ import annotations

from typing import Final

# Interval in minutes to exclude devices from a scan while they are home
CONF_HOME_INTERVAL: Final = "home_interval"
CONF_OPTIONS: Final = "scan_options"
DEFAULT_OPTIONS: Final = "-F --host-timeout 5s"
