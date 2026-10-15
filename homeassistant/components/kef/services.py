"""Services for the KEF Wireless Speakers integration."""

from aiokef.aiokef import DSP_OPTION_MAPPING
import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_MODE = "set_mode"
SERVICE_DESK_DB = "set_desk_db"
SERVICE_WALL_DB = "set_wall_db"
SERVICE_TREBLE_DB = "set_treble_db"
SERVICE_HIGH_HZ = "set_high_hz"
SERVICE_LOW_HZ = "set_low_hz"
SERVICE_SUB_DB = "set_sub_db"
SERVICE_UPDATE_DSP = "update_dsp"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the KEF Wireless Speakers integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MODE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Optional("desk_mode"): cv.boolean,
            probatio.Optional("wall_mode"): cv.boolean,
            probatio.Optional("phase_correction"): cv.boolean,
            probatio.Optional("high_pass"): cv.boolean,
            probatio.Optional("sub_polarity"): probatio.In(["-", "+"]),
            probatio.Optional("bass_extension"): probatio.In(
                ["Less", "Standard", "Extra"]
            ),
        },
        func="set_mode",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPDATE_DSP,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="update_dsp",
    )

    for name, which, option in (
        (SERVICE_DESK_DB, "desk_db", "db_value"),
        (SERVICE_WALL_DB, "wall_db", "db_value"),
        (SERVICE_TREBLE_DB, "treble_db", "db_value"),
        (SERVICE_HIGH_HZ, "high_hz", "hz_value"),
        (SERVICE_LOW_HZ, "low_hz", "hz_value"),
        (SERVICE_SUB_DB, "sub_db", "db_value"),
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
