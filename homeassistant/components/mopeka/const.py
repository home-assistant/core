"""Constants for the Mopeka integration."""

from typing import Final

from mopeka_iot_ble import MediumType

DOMAIN = "mopeka"

CONF_MEDIUM_TYPE: Final = "medium_type"

DEFAULT_MEDIUM_TYPE = MediumType.PROPANE.value
