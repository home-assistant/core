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
# Robots differ widely in how fast they answer: 900-series robots on 2.x
# firmware can take over 10 s to accept a connection and then publish their
# state in many messages over several seconds, newer ones in under a second.
SESSION_CONNECT_TIMEOUT = 30
TELEMETRY_QUIET_SECONDS = 2
TELEMETRY_MAX_SECONDS = 30
COMMAND_HOLD_SECONDS = 120
# Phases in which the robot is moving or about to; the session stays open.
ACTIVE_PHASES = frozenset({"run", "hmMidMsn", "hmPostMsn", "hmUsrDock", "evac"})
