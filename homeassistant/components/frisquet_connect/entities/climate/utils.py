import logging
from frisquet_connect.const import ZoneMode, ZoneSelector
from frisquet_connect.domains.site.zone import Zone
from homeassistant.components.climate.const import (
    HVACMode,
    PRESET_NONE,
    PRESET_BOOST,
    PRESET_HOME,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_SLEEP,
    PRESET_ECO,
)

_LOGGER = logging.getLogger(__name__)


def get_hvac_and_preset_mode_for_a_zone(
    zone: Zone,
) -> tuple[list[HVACMode], str, HVACMode]:
    # Inputs
    selector = zone.detail.selector
    mode = zone.detail.mode

    _LOGGER.debug(
        f"get_hvac_and_preset_mode_for_a_zone: selector={selector}, mode={mode}"
    )

    # Outputs
    available_preset_modes: list[str]
    hvac_mode: HVACMode
    preset_mode: str

    # AUTO
    if selector == ZoneSelector.AUTO:
        available_preset_modes = [PRESET_NONE, PRESET_HOME, PRESET_AWAY]
        if zone.detail.is_exemption_enabled:
            preset_mode = PRESET_HOME if mode == ZoneMode.COMFORT else PRESET_AWAY
        elif zone.is_boost_available and zone.detail.is_boosting:
            preset_mode = PRESET_BOOST
        else:
            preset_mode = PRESET_NONE
        hvac_mode = HVACMode.AUTO

    else:
        # MANUAL HEAT - COMFORT_PERMANENT or REDUCED_PERMANENT
        available_preset_modes = [PRESET_COMFORT, PRESET_SLEEP]
        hvac_mode = HVACMode.HEAT
        if selector == ZoneSelector.COMFORT_PERMANENT:
            preset_mode = PRESET_COMFORT
        elif selector == ZoneSelector.REDUCED_PERMANENT:
            preset_mode = PRESET_SLEEP
        # MANUAL HEAT - FROST_PROTECTION
        elif selector == ZoneSelector.FROST_PROTECTION:
            available_preset_modes = [PRESET_ECO]
            preset_mode = PRESET_ECO
            hvac_mode = HVACMode.OFF
        # UNKNOW
        else:
            available_preset_modes = [PRESET_NONE]
            preset_mode = PRESET_NONE
            hvac_mode = HVACMode.OFF

    if zone.is_boost_available and mode == ZoneMode.COMFORT:
        available_preset_modes = [PRESET_BOOST, *available_preset_modes]

    return (available_preset_modes, preset_mode, hvac_mode)


def get_target_temperature(zone: Zone) -> float | None:
    mode = zone.detail.mode
    if mode == ZoneMode.COMFORT:
        return zone.detail.comfort_temperature
    elif mode == ZoneMode.REDUCED:
        return zone.detail.reduced_temperature
    elif mode == ZoneMode.FROST_PROTECTION:
        return zone.detail.frost_protection_temperature
    else:
        return None
