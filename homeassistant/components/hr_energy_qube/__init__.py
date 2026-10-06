"""The Qube Heat Pump integration."""

from python_qube_heatpump import QubeClient, async_get_device_info

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN, MDNS_LOOKUP_TIMEOUT, PLATFORMS
from .coordinator import QubeCoordinator

type QubeConfigEntry = ConfigEntry[QubeCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> bool:
    """Set up Qube Heat Pump from a config entry."""
    client = QubeClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = QubeCoordinator(hass, client, entry)

    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if entry.unique_id is None:
        entry.async_create_background_task(
            hass, _async_set_unique_id(hass, entry), "hr_energy_qube unique id"
        )
    return True


async def _async_set_unique_id(hass: HomeAssistant, entry: QubeConfigEntry) -> None:
    """Give entries created without mDNS the controller's uuid as unique id."""
    aiozc = await zeroconf.async_get_async_instance(hass)
    device = await async_get_device_info(
        entry.data[CONF_HOST], aiozc, timeout=MDNS_LOOKUP_TIMEOUT
    )
    if device is None or hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, device.uuid
    ):
        return
    hass.config_entries.async_update_entry(entry, unique_id=device.uuid)


async def async_unload_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()
    return unload_ok
