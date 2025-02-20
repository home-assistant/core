"""Constants for the Satel Integra integration."""

from dataclasses import dataclass

from satel_integra.satel_integra import AsyncSatel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

DEFAULT_CONF_ARM_HOME_MODE = 1
DEFAULT_PORT = 7094
DEFAULT_ZONE_TYPE = "motion"

DOMAIN = "satel_integra"

CONF_DEVICE_CODE = "code"
CONF_DEVICE_PARTITIONS = "partitions"
CONF_ARM_HOME_MODE = "arm_home_mode"
CONF_ZONE_NAME = "name"
CONF_ZONE_TYPE = "type"
CONF_ZONES = "zones"
CONF_OUTPUTS = "outputs"
CONF_SWITCHABLE_OUTPUTS = "switchable_outputs"

ZONES = "zones"

SIGNAL_PANEL_MESSAGE = "satel_integra.panel_message"

SIGNAL_ZONES_UPDATED = "satel_integra.zones_updated"
SIGNAL_OUTPUTS_UPDATED = "satel_integra.outputs_updated"

SUPPORTED_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

type SatelConfigEntry = ConfigEntry[SatelData]


@dataclass
class SatelData:
    """Data for Satel Integra integration."""

    controller: AsyncSatel
