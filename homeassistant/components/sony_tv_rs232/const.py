"""Constants for the Sony TV RS-232 integration."""

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "sony_tv_rs232"
MANUFACTURER = "Sony"

# Sony TVs push nothing over RS-232, so the coordinator polls. In standby only
# the power state is asked for; a set-only (consumer) TV is never polled.
SCAN_INTERVAL = timedelta(seconds=60)

# Seconds after the TV reports power-on before re-querying it, giving the set
# time to finish booting.
POWER_ON_REFRESH_DELAY = 3.0
