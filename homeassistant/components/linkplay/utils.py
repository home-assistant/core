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
MANUFACTURER_WIIM: Final[str] = "WiiM"
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
MODELS_WIIM_AMP: Final[str] = "WiiM Amp"
MODELS_WIIM_MINI: Final[str] = "WiiM Mini"
MODELS_GGMM_GGMM_E2: Final[str] = "GGMM E2"
MODELS_MEDION_MD_43970: Final[str] = "Life P66970 (MD 43970)"
MODELS_GENERIC: Final[str] = "Generic"

PROJECTID_LOOKUP: Final[dict[str, tuple[str, str]]] = {
    "SMART_ZONE4_AMP": (MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_ZONE4),
    "SMART_HYDE": (MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_HYDE),
    "ARYLIC_S50": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_S50),
    "RP0016_S50PRO_S": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_S50_PRO),
    "RP0011_WB60_S": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_A30),
    "X-50": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_A50),
    "ARYLIC_A50S": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_A50S),
    "RP0011_WB60": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_AMP),
    "UP2STREAM_AMP_V3": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_AMP_V3),
    "UP2STREAM_AMP_V4": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_AMP_V4),
    "UP2STREAM_PRO_V3": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_PRO_V3),
    "ARYLIC_V20": (MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_PLATE_AMP),
    "UP2STREAM_MINI_V3": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "UP2STREAM_AMP_2P1": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "RP0014_A50C_S": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "ARYLIC_A30": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "ARYLIC_SUBWOOFER": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "ARYLIC_S50A": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "RP0010_D5_S": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "RP0001": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "RP0013_WA31S": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "RP0010_D5": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "RP0013_WA31S_S": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "RP0014_A50D_S": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "ARYLIC_A50TE": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "ARYLIC_A50N": (MANUFACTURER_ARYLIC, MODELS_GENERIC),
    "iEAST-02": (MANUFACTURER_IEAST, MODELS_IEAST_AUDIOCAST_M5),
    "WiiM_Amp_4layer": (MANUFACTURER_WIIM, MODELS_WIIM_AMP),
    "Muzo_Mini": (MANUFACTURER_WIIM, MODELS_WIIM_MINI),
    "GGMM_E2A": (MANUFACTURER_GGMM, MODELS_GGMM_GGMM_E2),
    "A16": (MANUFACTURER_MEDION, MODELS_MEDION_MD_43970),
}


def get_info_from_project(project: str) -> tuple[str, str]:
    """Get manufacturer and model info based on given project."""
    return PROJECTID_LOOKUP.get(project, (MANUFACTURER_GENERIC, MODELS_GENERIC))


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
