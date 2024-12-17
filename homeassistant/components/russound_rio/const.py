"""Constants used for Russound RIO."""

import asyncio

from aiorussound import CommandError
from aiorussound.const import FeatureFlag

from homeassistant.components.media_player import MediaPlayerEntityFeature

DOMAIN = "russound_rio"

RUSSOUND_RIO_EXCEPTIONS = (
    CommandError,
    ConnectionRefusedError,
    TimeoutError,
    asyncio.CancelledError,
)


CONNECT_TIMEOUT = 15

MP_FEATURES_BY_FLAG = {
    FeatureFlag.COMMANDS_ZONE_MUTE_OFF_ON: MediaPlayerEntityFeature.VOLUME_MUTE
}
