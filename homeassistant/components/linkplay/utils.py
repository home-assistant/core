"""Utilities for the LinkPlay component."""

from typing import Final

from aiohttp import ClientSession
from linkplay.utils import async_create_unverified_client_session

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, callback

from .const import DATA_SESSION, DOMAIN

MANUFACTURER_ARTSOUND: Final[str] = "ArtSound"
MANUFACTURER_ARYLIC: Final[str] = "Arylic"
MANUFACTURER_IEAST: Final[str] = "iEAST"
MANUFACTURER_GGMM: Final[str] = "GGMM"
MANUFACTURER_MEDION: Final[str] = "Medion"
MANUFACTURER_GENERIC: Final[str] = "Generic"
MODELS_ARTSOUND_SMART_ZONE4: Final[str] = "Smart Zone 4 AMP"
MODELS_ARTSOUND_SMART_HYDE: Final[str] = "Smart Hyde"
MODELS_ARYLIC_S50: Final[str] = "S50+"
MODELS_ARYLIC_S50_PRO: Final[str] = "S50 Pro"
MODELS_ARYLIC_A30: Final[str] = "A30"
MODELS_ARYLIC_A50: Final[str] = "A50"
MODELS_ARYLIC_A50S: Final[str] = "A50+"
MODELS_ARYLIC_UP2STREAM_AMP: Final[str] = "Up2Stream Amp 2.0"
MODELS_ARYLIC_UP2STREAM_AMP_V3: Final[str] = "Up2Stream Amp v3"
MODELS_ARYLIC_UP2STREAM_AMP_V4: Final[str] = "Up2Stream Amp v4"
MODELS_ARYLIC_UP2STREAM_PRO: Final[str] = "Up2Stream Pro v1"
MODELS_ARYLIC_UP2STREAM_PRO_V3: Final[str] = "Up2Stream Pro v3"
MODELS_ARYLIC_UP2STREAM_PLATE_AMP: Final[str] = "Up2Stream Plate Amp"
MODELS_IEAST_AUDIOCAST_M5: Final[str] = "AudioCast M5"
MODELS_GGMM_GGMM_E2: Final[str] = "GGMM E2"
MODELS_MEDION_MD_43970: Final[str] = "Life P66970 (MD 43970)"
MODELS_GENERIC: Final[str] = "Generic"


def get_info_from_project(project: str) -> tuple[str, str]:
    """Get manufacturer and model info based on given project."""
    match project:
        case "SMART_ZONE4_AMP":
            return MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_ZONE4
        case "SMART_HYDE":
            return MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_HYDE
        case "ARYLIC_S50":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_S50
        case "RP0016_S50PRO_S":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_S50_PRO
        case "RP0011_WB60_S":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_A30
        case "X-50":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_A50
        case "ARYLIC_A50S":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_A50S
        case "RP0011_WB60":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_AMP
        case "UP2STREAM_AMP_V3":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_AMP_V3
        case "UP2STREAM_AMP_V4":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_AMP_V4
        case "UP2STREAM_PRO_V3":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_PRO_V3
        case "ARYLIC_V20":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_PLATE_AMP
        case "UP2STREAM_MINI_V3":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "UP2STREAM_AMP_2P1":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "RP0014_A50C_S":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "ARYLIC_A30":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "ARYLIC_SUBWOOFER":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "ARYLIC_S50A":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "RP0010_D5_S":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "RP0001":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "RP0013_WA31S":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "RP0010_D5":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "RP0013_WA31S_S":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "RP0014_A50D_S":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "ARYLIC_A50TE":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "ARYLIC_A50N":
            return MANUFACTURER_ARYLIC, MODELS_GENERIC
        case "iEAST-02":
            return MANUFACTURER_IEAST, MODELS_IEAST_AUDIOCAST_M5
        case "GGMM_E2A":
            return MANUFACTURER_GGMM, MODELS_GGMM_GGMM_E2
        case "A16":
            return MANUFACTURER_MEDION, MODELS_MEDION_MD_43970
        case _:
            return MANUFACTURER_GENERIC, MODELS_GENERIC


async def async_get_client_session(hass: HomeAssistant) -> ClientSession:
    """Get a ClientSession that can be used with LinkPlay devices."""
    hass.data.setdefault(DOMAIN, {})
    if DATA_SESSION not in hass.data[DOMAIN]:
        clientsession: ClientSession = await async_create_unverified_client_session()

        @callback
        def _async_close_websession(event: Event) -> None:
            """Close websession."""
            clientsession.detach()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_websession)
        hass.data[DOMAIN][DATA_SESSION] = clientsession
        return clientsession

    session: ClientSession = hass.data[DOMAIN][DATA_SESSION]
    return session
