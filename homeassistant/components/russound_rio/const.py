"""Constants used for Russound RIO."""

import asyncio

from aiorussound import CommandException
from aiorussound.const import FeatureFlag

from homeassistant.components.media_player import MediaPlayerEntityFeature

DOMAIN = "russound_rio"

RUSSOUND_RIO_EXCEPTIONS = (
    CommandException,
    ConnectionRefusedError,
    TimeoutError,
    asyncio.CancelledError,
)


class NoPrimaryControllerException(Exception):
    """Thrown when the Russound device is not the primary unit in the RNET stack."""


CONNECT_TIMEOUT = 5

MP_FEATURES_BY_FLAG = {
    FeatureFlag.COMMANDS_ZONE_MUTE_OFF_ON: MediaPlayerEntityFeature.VOLUME_MUTE
}
