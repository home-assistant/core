"""const."""

from __future__ import annotations

from logging import Logger, getLogger

_LOGGER: Logger = getLogger(__package__)

COORDINATORS = "coordinators"

DATA_DISCOVERY_SERVICE = "refoss_discovery"

DISCOVERY_SCAN_INTERVAL = 30
DISCOVERY_TIMEOUT = 8
DISPATCH_DEVICE_DISCOVERED = "refoss_device_discovered"
DISPATCHERS = "dispatchers"

DOMAIN = "refoss"
COORDINATOR = "coordinator"

MAX_ERRORS = 2
