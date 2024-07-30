"""Constants for the Mopeka integration."""

from typing import Final

from mopeka_iot_ble import MediumType
import voluptuous as vol

DOMAIN = "mopeka"

CONF_MEDIUM_TYPE: Final = "medium_type"

DEFAULT_MEDIUM_TYPE = MediumType.PROPANE.value

BASE_SCHEMA = {
    vol.Required(CONF_MEDIUM_TYPE, default=DEFAULT_MEDIUM_TYPE): vol.In(
        {medium.value: medium.name for medium in MediumType}
    )
}
