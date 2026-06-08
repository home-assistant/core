"""The OSRAM infrared integration."""

from dataclasses import dataclass

from homeassistant.components.infrared import async_get_emitters
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_INFRARED_ENTITY_ID, CONF_INFRARED_RECEIVER_ENTITY_ID

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.LIGHT,
]


@dataclass(frozen=True, slots=True)
class OsramIrRuntimeData:
    """Runtime data for the OSRAM infrared integration."""

    infrared_entity_id: str
    infrared_receiver_entity_id: str | None


type OsramIrConfigEntry = ConfigEntry[OsramIrRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OsramIrConfigEntry,
) -> bool:
    """Set up OSRAM infrared from a config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]

    if infrared_entity_id not in async_get_emitters(hass):
        raise ConfigEntryNotReady(
            f"Infrared emitter entity {infrared_entity_id} is not available"
        )

    entry.runtime_data = OsramIrRuntimeData(
        infrared_entity_id=infrared_entity_id,
        infrared_receiver_entity_id=entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: OsramIrConfigEntry,
) -> bool:
    """Unload an OSRAM infrared config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
