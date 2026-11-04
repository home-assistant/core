"""Constants for the Snooz component."""

from pysnooz import SnoozDeviceModel

from homeassistant.const import Platform

DOMAIN = "snooz"
PLATFORMS: list[Platform] = [Platform.FAN]

CONF_FIRMWARE_VERSION = "firmware_version"

MANUFACTURER = "SNOOZ"
MODEL_NAMES: dict[SnoozDeviceModel, str] = {
    SnoozDeviceModel.ORIGINAL: "Original",
    SnoozDeviceModel.PRO: "Pro",
    SnoozDeviceModel.BREEZ: "Breez",
}

SERVICE_TRANSITION_ON = "transition_on"
SERVICE_TRANSITION_OFF = "transition_off"

ATTR_VOLUME = "volume"
ATTR_DURATION = "duration"

DEFAULT_TRANSITION_DURATION = 20
