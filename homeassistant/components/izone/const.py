"""Constants used by the izone component."""

from datetime import timedelta

DOMAIN = "izone"

DATA_CONFIG = "izone_config"

TIMEOUT_DISCOVERY = 5
DISCOVERY_IDLE_SECONDS = 4 * TIMEOUT_DISCOVERY
# Match legacy pizone DISCOVERY_SLEEP (~5 min) for new-device hunt cadence.
DISCOVERY_SCAN_INTERVAL = timedelta(minutes=5)
