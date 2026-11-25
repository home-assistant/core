"""Services for the KEF Wireless Speakers integration."""

from enum import StrEnum

from aiokef.aiokef import DSP_OPTION_MAPPING
import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class KefService(StrEnum):
    """Store keys for KEF services."""

    UPDATE_DSP = "update_dsp"
    SET_MODE = "set_mode"
    SET_DESK_DB = "set_desk_db"
    SET_WALL_DB = "set_wall_db"
    SET_TREBLE_DB = "set_treble_db"
    SET_HIGH_HZ = "set_high_hz"
    SET_LOW_HZ = "set_low_hz"
    SET_SUB_DB = "set_sub_db"


class KefServiceArgument(StrEnum):
    """Store keys for KEF service arguments."""

    DESK_MODE = "desk_mode"
    WALL_MODE = "wall_mode"
    PHASE_CORRECTION = "phase_correction"
    HIGH_PASS = "high_pass"
    SUB_POLARITY = "sub_polarity"
    BASS_EXTENSION = "bass_extension"
    DB_VALUE = "db_value"
    HZ_VALUE = "hz_value"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the KEF Wireless Speakers integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        KefService.SET_MODE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Optional(KefServiceArgument.DESK_MODE): cv.boolean,
            probatio.Optional(KefServiceArgument.WALL_MODE): cv.boolean,
            probatio.Optional(KefServiceArgument.PHASE_CORRECTION): cv.boolean,
            probatio.Optional(KefServiceArgument.HIGH_PASS): cv.boolean,
            probatio.Optional(KefServiceArgument.SUB_POLARITY): probatio.In(["-", "+"]),
            probatio.Optional(KefServiceArgument.BASS_EXTENSION): probatio.In(
                ["Less", "Standard", "Extra"]
            ),
        },
        func="set_mode",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        KefService.UPDATE_DSP,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="update_dsp",
    )

    for name, which, option in (
        (KefService.SET_DESK_DB, "desk_db", KefServiceArgument.DB_VALUE),
        (KefService.SET_WALL_DB, "wall_db", KefServiceArgument.DB_VALUE),
        (KefService.SET_TREBLE_DB, "treble_db", KefServiceArgument.DB_VALUE),
        (KefService.SET_HIGH_HZ, "high_hz", KefServiceArgument.HZ_VALUE),
        (KefService.SET_LOW_HZ, "low_hz", KefServiceArgument.HZ_VALUE),
        (KefService.SET_SUB_DB, "sub_db", KefServiceArgument.DB_VALUE),
    ):
        options = DSP_OPTION_MAPPING[which]
        dtype = type(options[0])  # int or float
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            name,
            entity_domain=MEDIA_PLAYER_DOMAIN,
            schema={
                probatio.Required(option): probatio.All(
                    probatio.Coerce(float), probatio.Coerce(dtype), probatio.In(options)
                )
            },
            func=f"set_{which}",
        )
