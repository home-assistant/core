"""The rest component constants."""

from homeassistant.util.ssl import SSLCipherList

DOMAIN = "rest"

DEFAULT_METHOD = "GET"
DEFAULT_VERIFY_SSL = True
DEFAULT_SSL_CIPHER_LIST = SSLCipherList.PYTHON_DEFAULT
DEFAULT_FORCE_UPDATE = False
DEFAULT_ENCODING = "UTF-8"
CONF_ENCODING = "encoding"
CONF_SSL_CIPHER_LIST = "ssl_cipher_list"

DEFAULT_BINARY_SENSOR_NAME = "REST Binary Sensor"
DEFAULT_SENSOR_NAME = "REST Sensor"
CONF_JSON_ATTRS = "json_attributes"
CONF_JSON_ATTRS_PATH = "json_attributes_path"

REST_IDX = "rest_idx"
PLATFORM_IDX = "platform_idx"

COORDINATOR = "coordinator"
REST = "rest"

REST_DATA = "rest_data"

METHODS = ["POST", "GET"]
