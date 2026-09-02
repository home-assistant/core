"""The roomba constants."""

from homeassistant.const import Platform

DOMAIN = "roomba"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.VACUUM]
CONF_CERT = "certificate"
CONF_CONN_MODE = "connection_mode"
CONF_CONTINUOUS = "continuous"
CONF_PERIODIC = "periodic"
CONF_ADHOC = "adhoc"
CONNECTION_MODES = [CONF_CONTINUOUS, CONF_PERIODIC, CONF_ADHOC]
CONF_BLID = "blid"
DEFAULT_CERT = "/etc/ssl/certs/ca-certificates.crt"
DEFAULT_MODE = CONF_CONTINUOUS
DEFAULT_DELAY = 30
ROOMBA_SESSION = "roomba_session"
