"""The BSB-Lan integration."""

import dataclasses

from bsblan import BSBLAN, BSBLANConfig, Device, Info, StaticState

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

from .const import CONF_PASSKEY, DOMAIN
from .coordinator import BSBLanUpdateCoordinator

PLATFORMS = [Platform.CLIMATE]


@dataclasses.dataclass
class BSBLanData:
    """BSBLan data stored in the Home Assistant data object."""

    coordinator: BSBLanUpdateCoordinator
    client: BSBLAN
    device: Device
    info: Info
    static: StaticState


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BSB-Lan from a config entry."""

    # create config using BSBLANConfig
    config = BSBLANConfig(
        host=entry.data[CONF_HOST],
        passkey=entry.data[CONF_PASSKEY],
        port=entry.data[CONF_PORT],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    # create BSBLAN client
    session = async_get_clientsession(hass)
    bsblan = BSBLAN(config, session)

    # Create and perform first refresh of the coordinator
    coordinator = BSBLanUpdateCoordinator(hass, entry, bsblan)
    await coordinator.async_config_entry_first_refresh()

    # Fetch all required data concurrently
    device = await bsblan.device()
    info = await bsblan.info()
    static = await bsblan.static_values()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = BSBLanData(
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
