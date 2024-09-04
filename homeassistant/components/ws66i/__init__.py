"""The Soundavo WS66i 6-Zone Amplifier integration."""

from __future__ import annotations

import logging

from pyws66i import WS66i, get_ws66i

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SOURCES, DOMAIN
from .coordinator import Ws66iDataUpdateCoordinator
from .models import SourceRep, Ws66iData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]


@callback
def _get_sources_from_dict(data) -> SourceRep:
    sources_config = data[CONF_SOURCES]

    # Dict index to custom name
    source_id_name = {int(index): name for index, name in sources_config.items()}

    # Dict custom name to index
    source_name_id = {v: k for k, v in source_id_name.items()}

    # List of custom names
    source_names = sorted(source_name_id.keys(), key=lambda v: source_name_id[v])

    return SourceRep(source_id_name, source_name_id, source_names)


def _find_zones(hass: HomeAssistant, ws66i: WS66i) -> list[int]:
    """Generate zones list by searching for presence of zones."""
    # Zones 11 - 16 are the master amp
    # Zones 21,31 - 26,36 are the daisy-chained amps
    zone_list = []
    for amp_num in range(1, 4):
        if amp_num > 1:
            # Don't add entities that aren't present
            status = ws66i.zone_status(amp_num * 10 + 1)
            if status is None:
                break

        for zone_num in range(1, 7):
            zone_id = (amp_num * 10) + zone_num
            zone_list.append(zone_id)

    _LOGGER.info("Detected %d amp(s)", amp_num - 1)
    return zone_list


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Soundavo WS66i 6-Zone Amplifier from a config entry."""
    # Get the source names from the options flow
    options: dict[str, dict[str, str]]
    options = {CONF_SOURCES: entry.options[CONF_SOURCES]}
    # Get the WS66i object and open up a connection to it
    ws66i = get_ws66i(entry.data[CONF_IP_ADDRESS])
    try:
        await hass.async_add_executor_job(ws66i.open)
    except ConnectionError as err:
        # Amplifier is probably turned off
        raise ConfigEntryNotReady("Could not connect to WS66i Amp. Is it off?") from err

    # Create the zone Representation dataclass
    source_rep: SourceRep = _get_sources_from_dict(options)

    # Create a list of discovered zones
    zones = await hass.async_add_executor_job(_find_zones, hass, ws66i)

    # Create the coordinator for the WS66i
    coordinator: Ws66iDataUpdateCoordinator = Ws66iDataUpdateCoordinator(
        hass,
        ws66i,
        zones,
    )

    # Fetch initial data, retry on failed poll
    await coordinator.async_config_entry_first_refresh()

    # Create the Ws66iData data class save it to hass
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = Ws66iData(
        host_ip=entry.data[CONF_IP_ADDRESS],
        device=ws66i,
        sources=source_rep,
        coordinator=coordinator,
        zones=zones,
    )

    @callback
    def shutdown(event):
        """Close the WS66i connection to the amplifier."""
        ws66i.close()

    entry.async_on_unload(entry.add_update_listener(_update_listener))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        ws66i: WS66i = hass.data[DOMAIN][entry.entry_id].device
        ws66i.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
