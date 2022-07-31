"""The Picnic integration."""

from python_picnic_api import PicnicAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_API, CONF_COORDINATOR, CONF_COUNTRY_CODE, DOMAIN
from .coordinator import PicnicUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


def create_picnic_client(entry: ConfigEntry):
    """Create an instance of the PicnicAPI client."""
    return PicnicAPI(
        auth_token=entry.data.get(CONF_ACCESS_TOKEN),
        country_code=entry.data.get(CONF_COUNTRY_CODE),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Picnic from a config entry."""
    picnic_client = await hass.async_add_executor_job(create_picnic_client, entry)
    picnic_coordinator = PicnicUpdateCoordinator(hass, picnic_client, entry)

    # Fetch initial data so we have data when entities subscribe
    await picnic_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_API: picnic_client,
        CONF_COORDINATOR: picnic_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
