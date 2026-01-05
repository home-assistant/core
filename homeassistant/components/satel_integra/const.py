"""Constants for the Satel Integra integration."""

from satel_integra.satel_integra import AsyncSatel

from homeassistant.config_entries import ConfigEntry

DEFAULT_CONF_ARM_HOME_MODE = 1
DEFAULT_PORT = 7094
DEFAULT_ZONE_TYPE = "motion"

DOMAIN = "satel_integra"

SUBENTRY_TYPE_PARTITION = "partition"
SUBENTRY_TYPE_ZONE = "zone"
SUBENTRY_TYPE_OUTPUT = "output"
SUBENTRY_TYPE_SWITCHABLE_OUTPUT = "switchable_output"

CONF_PARTITION_NUMBER = "partition_number"
CONF_ZONE_NUMBER = "zone_number"
CONF_OUTPUT_NUMBER = "output_number"
CONF_SWITCHABLE_OUTPUT_NUMBER = "switchable_output_number"

CONF_DEVICE_PARTITIONS = "partitions"
CONF_ARM_HOME_MODE = "arm_home_mode"
CONF_ZONE_TYPE = "type"
CONF_ZONES = "zones"
CONF_OUTPUTS = "outputs"
CONF_SWITCHABLE_OUTPUTS = "switchable_outputs"

ZONES = "zones"


SIGNAL_PANEL_MESSAGE = "satel_integra.panel_message"

SIGNAL_ZONES_UPDATED = "satel_integra.zones_updated"
SIGNAL_OUTPUTS_UPDATED = "satel_integra.outputs_updated"

type SatelConfigEntry = ConfigEntry[AsyncSatel]
