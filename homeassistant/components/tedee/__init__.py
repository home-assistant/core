import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url
from pytedee_async import TedeeClient

from .const import DOMAIN, CONF_HOME_ASSISTANT_ACCESS_TOKEN, CONF_LOCAL_ACCESS_TOKEN
from .coordinator import TedeeApiCoordinator
from .views import TedeeWebhookView

PLATFORMS = ["lock", "sensor", "button"]

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    logging.debug("Setting up Tedee integration...")
    hass.data.setdefault(DOMAIN, {})

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Integration setup"""
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    pak = entry.data.get(CONF_ACCESS_TOKEN)
    host = entry.data.get(CONF_HOST)
    local_access_token = entry.data.get(CONF_LOCAL_ACCESS_TOKEN)
    home_assistant_token = entry.data.get(CONF_HOME_ASSISTANT_ACCESS_TOKEN, "")

    tedee_client = TedeeClient(pak, local_access_token, host)

    hass.data[DOMAIN][entry.entry_id] = coordinator = TedeeApiCoordinator(hass, tedee_client)

    await coordinator.async_config_entry_first_refresh()

    # Setup webhook if long lived access token
    if home_assistant_token != "":

        instance_url = get_url(hass)
        _LOGGER.debug("Registering webhook at %s/api/tedee/webhook", instance_url)
        hass.http.register_view(TedeeWebhookView(coordinator))
        headers = [
            # {
            #     "Authorization": f"Bearer {home_assistant_token}"
            # }
        ]
        # TODO: Switch back to correct URL
        # await tedee_client.register_webhook(instance_url + "/api/tedee/webhook", headers)
        await tedee_client.register_webhook(instance_url + "/tedee", headers)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
    return True


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    # cleanup webhooks
    # coordinator = hass.data[DOMAIN][entry.entry_id]
    # try:
    #     await coordinator._tedee_client.delete_webhooks()
    # except Exception as ex:
    #     _LOGGER.warn("Error while deleting webhooks: %s", ex)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN] = {}

    return unload_ok
        