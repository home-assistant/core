"""The Clicky Web Analytics integration."""

from pyclicky import ClickyClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from .coordinator import ClickyConfigEntry, ClickyCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ClickyConfigEntry) -> bool:
    """Set up Clicky Web Analytics from a config entry."""

    session = async_get_clientsession(hass)
    client = ClickyClient(
        site_id=entry.data[CONF_SITE_ID],
        sitekey=entry.data[CONF_SITEKEY],
        session=session,
    )

    coordinator = ClickyCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ClickyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


def device_info(name: str) -> DeviceInfo:
    """Return device registry information."""
    return DeviceInfo(
        identifiers={(DOMAIN, name)},
        entry_type=DeviceEntryType.SERVICE,
        name=f"Clicky: {name}",
        manufacturer="Clicky Web Analytics",
    )
