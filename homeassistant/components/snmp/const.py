"""SNMP constants."""
CONF_ACCEPT_ERRORS = 'accept_errors'
CONF_AUTH_KEY = 'auth_key'
CONF_AUTH_PROTOCOL = 'auth_protocol'
CONF_BASEOID = 'baseoid'
CONF_COMMUNITY = 'community'
CONF_DEFAULT_VALUE = 'default_value'
CONF_PRIV_KEY = 'priv_key'
CONF_PRIV_PROTOCOL = 'priv_protocol'
CONF_VERSION = 'version'

DEFAULT_AUTH_PROTOCOL = 'none'
DEFAULT_COMMUNITY = 'public'
DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'SNMP'
DEFAULT_PORT = '161'
DEFAULT_PRIV_PROTOCOL = 'none'
DEFAULT_VERSION = '1'

SNMP_VERSIONS = {
    '1': 0,
    '2c': 1,
    '3': None
}

MAP_AUTH_PROTOCOLS = {
    'none': 'usmNoAuthProtocol',
    'hmac-md5': 'usmHMACMD5AuthProtocol',
    'hmac-sha': 'usmHMACSHAAuthProtocol',
    'hmac128-sha224': 'usmHMAC128SHA224AuthProtocol',
    'hmac192-sha256': 'usmHMAC192SHA256AuthProtocol',
    'hmac256-sha384': 'usmHMAC256SHA384AuthProtocol',
    'hmac384-sha512': 'usmHMAC384SHA512AuthProtocol',
}

MAP_PRIV_PROTOCOLS = {
    'none': 'usmNoPrivProtocol',
    'des': 'usmDESPrivProtocol',
    '3des-ede': 'usm3DESEDEPrivProtocol',
    'aes-cfb-128': 'usmAesCfb128Protocol',
    'aes-cfb-192': 'usmAesCfb192Protocol',
    'aes-cfb-256': 'usmAesCfb256Protocol',
}
