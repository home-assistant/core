"""The rest component constants."""

from homeassistant.const import Platform
from homeassistant.util.ssl import SSLCipherList

DOMAIN = "rest"

DEFAULT_METHOD = "GET"
DEFAULT_VERIFY_SSL = True
DEFAULT_SSL_CIPHER_LIST = SSLCipherList.PYTHON_DEFAULT
DEFAULT_FORCE_UPDATE = False
DEFAULT_ENCODING = "UTF-8"
DEFAULT_BINARY_SENSOR_NAME = "REST Binary Sensor"
DEFAULT_SENSOR_NAME = "REST Sensor"

DOCS_URL_TEMPLATE_DATA_PROCESSING = "https://www.home-assistant.io/docs/templating/where-to-use/#processing-incoming-data"
DOCS_URL_AVAILABILTY = (
    "https://www.home-assistant.io/integrations/template/#availability"
)
DOCS_URL_XML_CONVERT_SPEC = (
    "https://www.xml.com/pub/a/2006/05/31/converting-between-xml-and-json.html"
)
DOCS_URL_JSONPATH = "https://goessner.net/articles/JsonPath/"

CONF_ENCODING = "encoding"
CONF_JSON_ATTRS = "json_attributes"
CONF_JSON_ATTRS_PATH = "json_attributes_path"
CONF_PAYLOAD_TEMPLATE = "payload_template"
CONF_SSL_CIPHER_LIST = "ssl_cipher_list"
CONF_SSL_SECTION = "ssl_section"

REST_IDX = "rest_idx"
PLATFORM_IDX = "platform_idx"

COORDINATOR = "coordinator"
REST = "rest"

REST_DATA = "rest_data"

METHODS = ["POST", "GET"]

XML_MIME_TYPES = (
    "application/rss+xml",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
)

CONFIG_ENTRY_PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
