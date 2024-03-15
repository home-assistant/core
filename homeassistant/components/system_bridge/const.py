"""Constants for the System Bridge integration."""

from datetime import timedelta

DOMAIN = "system_bridge"

SCAN_INTERVAL = timedelta(seconds=10)

MODULES = [
    "battery",
    "cpu",
    "disks",
    "displays",
    "gpus",
    "media",
    "memory",
    "processes",
    "system",
]
