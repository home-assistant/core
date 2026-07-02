"""The Panasonic Window Air Conditioner (Hong Kong/Macau) integration.

Controls Panasonic window / through-the-wall air conditioners sold in Hong Kong
and Macau (CW-HU / CW-HZ / CW-SU / CW-SUL families) over the Home Assistant
``infrared`` platform. Reverse-engineered and verified on a CW-HU70ZA.
"""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DEFAULT_FAN,
    DEFAULT_MODE,
    DEFAULT_SWING,
    DEFAULT_TEMP,
)

PLATFORMS = [Platform.BUTTON, Platform.CLIMATE, Platform.SWITCH]


@dataclass
class PanasonicWindowAcHKRuntimeData:
    """Shared assumed state for one air conditioner.

    Infrared is one-way, so the state cannot be read back from the unit. The
    climate entity and the nanoeX switch share this object because nanoeX lives
    inside the full state frame and toggling it must re-assert mode, temperature,
    fan and swing.
    """

    infrared_emitter_entity_id: str
    power: bool = False
    mode: str = DEFAULT_MODE
    temp: float = DEFAULT_TEMP
    fan: str = DEFAULT_FAN
    swing: str = DEFAULT_SWING
    nanoex: bool = False


type PanasonicWindowAcHKConfigEntry = ConfigEntry[PanasonicWindowAcHKRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: PanasonicWindowAcHKConfigEntry
) -> bool:
    """Set up a Panasonic window air conditioner from a config entry."""
    entry.runtime_data = PanasonicWindowAcHKRuntimeData(
        infrared_emitter_entity_id=entry.data[CONF_INFRARED_EMITTER_ENTITY_ID],
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PanasonicWindowAcHKConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
