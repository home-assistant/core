"""Constants for the Onkyo integration."""

import typing
from typing import Literal

from aioonkyo import HDMIOutputParam, InputSourceParam, ListeningModeParam, Zone

DOMAIN = "onkyo"

DEVICE_INTERVIEW_TIMEOUT = 5
DEVICE_DISCOVERY_TIMEOUT = 5

type VolumeResolution = Literal[50, 80, 100, 200]
OPTION_VOLUME_RESOLUTION = "volume_resolution"
OPTION_VOLUME_RESOLUTION_DEFAULT: VolumeResolution = 50
VOLUME_RESOLUTION_ALLOWED: tuple[VolumeResolution, ...] = typing.get_args(
    VolumeResolution.__value__
)

OPTION_MAX_VOLUME = "max_volume"
OPTION_MAX_VOLUME_DEFAULT = 100.0

OPTION_INPUT_SOURCES = "input_sources"
OPTION_LISTENING_MODES = "listening_modes"

InputSource = InputSourceParam
ListeningMode = ListeningModeParam
HDMIOutput = HDMIOutputParam

ZONES = {
    Zone.MAIN: "Main",
    Zone.ZONE2: "Zone 2",
    Zone.ZONE3: "Zone 3",
    Zone.ZONE4: "Zone 4",
}


LEGACY_HDMI_OUTPUT_MAPPING = {
    HDMIOutput.ANALOG: "no,analog",
    HDMIOutput.MAIN: "yes,out",
    HDMIOutput.SUB: "out-sub,sub,hdbaset",
    HDMIOutput.BOTH: "both,sub",
    HDMIOutput.BOTH_MAIN: "both",
    HDMIOutput.BOTH_SUB: "both",
}

LEGACY_REV_HDMI_OUTPUT_MAPPING = {
    "analog": HDMIOutput.ANALOG,
    "both": HDMIOutput.BOTH_SUB,
    "hdbaset": HDMIOutput.SUB,
    "no": HDMIOutput.ANALOG,
    "out": HDMIOutput.MAIN,
    "out-sub": HDMIOutput.SUB,
    "sub": HDMIOutput.BOTH,
    "yes": HDMIOutput.MAIN,
}
