"""The KlikAanKlikUit RC integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_TRANSMITTER


@dataclass(slots=True)
class KlikAanKlikUitRuntimeData:
    """Runtime data for the KlikAanKlikUit integration."""

    transmitter_entity_id: str


type KlikAanKlikUitConfigEntry = ConfigEntry[KlikAanKlikUitRuntimeData]


PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(
    hass: HomeAssistant, entry: KlikAanKlikUitConfigEntry
) -> bool:
    """Setup KlikAanKlikUit RC from a config entry."""
    transmitter_entity_id = entry.data[CONF_TRANSMITTER]
    if hass.states.get(transmitter_entity_id) is None:
        raise ConfigEntryNotReady(
            f"RF transmitter entity {transmitter_entity_id} is not available"
        )

    entry.runtime_data = KlikAanKlikUitRuntimeData(
        transmitter_entity_id=transmitter_entity_id
    )
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: KlikAanKlikUitConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_listener(
    hass: HomeAssistant, entry: KlikAanKlikUitConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
