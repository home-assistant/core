"""The roomba constants."""

from homeassistant.const import Platform

DOMAIN = "roomba"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.VACUUM]
CONF_CERT = "certificate"
CONF_CONTINUOUS = "continuous"
CONF_BLID = "blid"
DEFAULT_CERT = "/etc/ssl/certs/ca-certificates.crt"
DEFAULT_CONTINUOUS = True
DEFAULT_DELAY = 1
ROOMBA_SESSION = "roomba_session"
