"""The BSB-Lan integration."""
import dataclasses

from bsblan import BSBLAN, Device, Info, State, StaticState

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_PASSKEY, DOMAIN, LOGGER, SCAN_INTERVAL

PLATFORMS = [Platform.CLIMATE]


@dataclasses.dataclass
class HomeAssistantBSBLANData:
    """BSBLan data stored in the Home Assistant data object."""

    coordinator: DataUpdateCoordinator[State]
    client: BSBLAN
    device: Device
    info: Info
    static: StaticState


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BSB-Lan from a config entry."""

    session = async_get_clientsession(hass)
    bsblan = BSBLAN(
        entry.data[CONF_HOST],
        passkey=entry.data[CONF_PASSKEY],
        port=entry.data[CONF_PORT],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        session=session,
    )

    coordinator: DataUpdateCoordinator[State] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
        update_interval=SCAN_INTERVAL,
        update_method=bsblan.state,
    )
    await coordinator.async_config_entry_first_refresh()

    device = await bsblan.device()
    info = await bsblan.info()
    static = await bsblan.static_values()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = HomeAssistantBSBLANData(
        client=bsblan,
        coordinator=coordinator,
        device=device,
        info=info,
        static=static,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload BSBLAN config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok
