"""SNMP constants."""

from datetime import timedelta
from typing import Final

from pysnmp.proto import errind

DOMAIN = "snmp"

CONF_ACCEPT_ERRORS = "accept_errors"
CONF_AUTH_KEY = "auth_key"
CONF_AUTH_PROTOCOL = "auth_protocol"
CONF_BASEOID = "baseoid"
CONF_COMMUNITY = "community"
CONF_CONTEXT_NAME = "context_name"
CONF_DEFAULT_VALUE = "default_value"
CONF_PRIV_KEY = "priv_key"
CONF_PRIV_PROTOCOL = "priv_protocol"
CONF_VERSION = "version"
CONF_VARTYPE = "vartype"

# Subentry types, one per capability of an SNMP device
SUBENTRY_TYPE_DEVICE_TRACKER = "device_tracker"

DEFAULT_AUTH_PROTOCOL = "none"
DEFAULT_COMMUNITY = "public"
DEFAULT_HOST = "localhost"
DEFAULT_NAME = "SNMP"
DEFAULT_PORT = 161
DEFAULT_PRIV_PROTOCOL = "none"
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_RETRIES = 1
DEFAULT_TIMEOUT = 8
DEFAULT_VERSION = "1"
DEFAULT_VARTYPE = "none"

# Polling of the config entry device tracker. The YAML sensor platform keeps its
# own 10 second interval until it is migrated.
DEFAULT_SCAN_INTERVAL = timedelta(seconds=DEFAULT_INTERVAL_SECONDS)


SNMP_VERSIONS = {"1": 0, "2c": 1, "3": None}

MAP_AUTH_PROTOCOLS = {
    "none": "usmNoAuthProtocol",
    "hmac-md5": "usmHMACMD5AuthProtocol",
    "hmac-sha": "usmHMACSHAAuthProtocol",
    "hmac128-sha224": "usmHMAC128SHA224AuthProtocol",
    "hmac192-sha256": "usmHMAC192SHA256AuthProtocol",
    "hmac256-sha384": "usmHMAC256SHA384AuthProtocol",
    "hmac384-sha512": "usmHMAC384SHA512AuthProtocol",
}

MAP_PRIV_PROTOCOLS = {
    "none": "usmNoPrivProtocol",
    "des": "usmDESPrivProtocol",
    "3des-ede": "usm3DESEDEPrivProtocol",
    "aes-cfb-128": "usmAesCfb128Protocol",
    "aes-cfb-192": "usmAesCfb192Protocol",
    "aes-cfb-256": "usmAesCfb256Protocol",
}

# Indications which mean the authentication or privacy keys are wrong, as
# opposed to a transient network failure. The indication objects are unhashable.
USM_WRONG_DIGEST_INDICATIONS: Final = (
    errind.wrongDigest,
    errind.decryptionError,
)

# Indications which mean the agent does not accept the user or the selected
# security level and protocols.
AUTH_ERROR_INDICATIONS: Final = (
    errind.unknownCommunityName,
    errind.unknownUserName,
    errind.unknownSecurityName,
    errind.unsupportedSecurityLevel,
    errind.unsupportedSecurityModel,
    errind.unsupportedAuthProtocol,
    errind.unsupportedPrivProtocol,
    errind.authenticationFailure,
    errind.authenticationError,
)

# Indications which mean the requested SNMPv3 context does not exist on the
# agent, which is a fixable configuration mistake rather than a network problem.
CONTEXT_ERROR_INDICATIONS: Final = (errind.noSuchContext,)

# Any indication which means the credentials are not accepted, so reauthenticating
# can fix it.
INVALID_CREDENTIAL_INDICATIONS: Final = (
    *USM_WRONG_DIGEST_INDICATIONS,
    *AUTH_ERROR_INDICATIONS,
)

# MAC columns of IP-indexed tables, where the row index ends with the device
# IPv4 address. Tables indexed by the MAC (e.g. bridge forwarding tables) use the
# same OID suffix for something else.
IP_INDEXED_MAC_OIDS: Final = (
    (1, 3, 6, 1, 2, 1, 4, 22, 1, 2),  # ipNetToMediaPhysAddress (ARP)
    (1, 3, 6, 1, 2, 1, 3, 1, 1, 2),  # atPhysAddress (RFC 1213 ARP)
)
