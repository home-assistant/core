"""The tests for Satel Integra integration."""

from types import MappingProxyType

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.satel_integra import (
    CONF_ARM_HOME_MODE,
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)
from homeassistant.components.satel_integra.const import DEFAULT_PORT
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT

MOCK_CONFIG_DATA = {CONF_HOST: "192.168.0.2", CONF_PORT: DEFAULT_PORT}
MOCK_CONFIG_OPTIONS = {CONF_CODE: "1234"}

MOCK_PARTITION_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_PARTITION,
    subentry_id="ID_PARTITION",
    unique_id="partition_1",
    title="Home (1)",
    data=MappingProxyType(
        {
            CONF_NAME: "Home",
            CONF_ARM_HOME_MODE: 1,
            CONF_PARTITION_NUMBER: 1,
        }
    ),
)

MOCK_ZONE_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_ZONE,
    subentry_id="ID_ZONE",
    unique_id="zone_1",
    title="Zone (1)",
    data=MappingProxyType(
        {
            CONF_NAME: "Zone",
            CONF_ZONE_TYPE: BinarySensorDeviceClass.MOTION,
            CONF_ZONE_NUMBER: 1,
        }
    ),
)

MOCK_OUTPUT_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_OUTPUT,
    subentry_id="ID_OUTPUT",
    unique_id="output_1",
    title="Output (1)",
    data=MappingProxyType(
        {
            CONF_NAME: "Output",
            CONF_ZONE_TYPE: BinarySensorDeviceClass.SAFETY,
            CONF_OUTPUT_NUMBER: 1,
        }
    ),
)

MOCK_SWITCHABLE_OUTPUT_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    subentry_id="ID_SWITCHABLE_OUTPUT",
    unique_id="switchable_output_1",
    title="Switchable Output (1)",
    data=MappingProxyType(
        {
            CONF_NAME: "Switchable Output",
            CONF_SWITCHABLE_OUTPUT_NUMBER: 1,
        }
    ),
)
