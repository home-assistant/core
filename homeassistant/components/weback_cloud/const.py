"""Constants for the Weback Cloud Integration integration."""
from collections.abc import Iterable

DOMAIN: str = "weback_cloud"
PLATFORMS: Iterable[str] = ["vacuum"]
SUPPORTED_DEVICES: Iterable[str] = ["_CLEAN_ROBOT"]
CONF_REGION: str = "region"
CONF_PHONE_NUMBER: str = "phone_number"
CONF_PASSWORD: str = "password"
ATTR_ERROR: str = "error"
ATTR_COMPONENT_PREFIX: str = "component_"
TYPE_WEBACK_CLOUD: str = "Weback Cloud"
THING_NAME: str = "Thing_Name"
WEBACK_DEVICES: str = "devices"
