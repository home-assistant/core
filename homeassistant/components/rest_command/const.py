"""Constants for the RESTful Command integration."""

from typing import Final

DOMAIN: Final = "rest_command"

AUTHENTICATION_BEARER: Final = "bearer"
AUTHENTICATION_NONE: Final = "none"

CONF_CONTENT_TYPE: Final = "content_type"
CONF_ENDPOINT_NAME: Final = "endpoint_name"
CONF_INSECURE_CIPHER: Final = "insecure_cipher"
CONF_SKIP_URL_ENCODING: Final = "skip_url_encoding"
SERVICE_CALL_ENDPOINT: Final = "call_endpoint"

DEFAULT_METHOD: Final = "get"
DEFAULT_PAYLOAD: Final = '{\n  "message": "The event occurred"\n}'
DEFAULT_TIMEOUT: Final = 10
DEFAULT_VERIFY_SSL: Final = True

SUPPORTED_REST_METHODS: Final = ["get", "patch", "post", "put", "delete"]
