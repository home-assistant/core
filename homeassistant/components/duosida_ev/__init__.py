"""The Duosida EV Charger integration."""

from duosida_ev import DuosidaClient

from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .coordinator import DuosidaConfigEntry, DuosidaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: DuosidaConfigEntry) -> None:
    """Set up Duosida EV Charger from a config entry."""
    coordinator = DuosidaCoordinator(hass, entry, DuosidaClient(entry.data[CONF_HOST]))

    async def _async_close_session(_event: Event) -> None:
        # Unload doesn't run on stop; a session that ends without a clean
        # close can keep the charger refusing connections for a long time.
        await coordinator.async_shutdown()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_session)
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: DuosidaConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
