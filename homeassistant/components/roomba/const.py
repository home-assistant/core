"""The roomba constants."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "roomba"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.VACUUM]
CONF_CERT = "certificate"
CONF_BLID = "blid"
DEFAULT_CERT = "/etc/ssl/certs/ca-certificates.crt"
ROOMBA_SESSION = "roomba_session"
CONF_CONTINUOUS = "continuous"
DEFAULT_CONTINUOUS = True

PERIODIC_UPDATE_INTERVAL = timedelta(minutes=5)
TELEMETRY_SETTLE_SECONDS = 10
COMMAND_HOLD_SECONDS = 120
# Phases in which the robot is moving or about to; the session stays open.
ACTIVE_PHASES = frozenset({"run", "hmMidMsn", "hmPostMsn", "hmUsrDock", "evac"})
