"""Init the tedee component."""
import logging

from pytedee_async import TedeeAuthException, TedeeClientException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_HOME_ASSISTANT_ACCESS_TOKEN, DOMAIN
from .coordinator import TedeeApiCoordinator
from .views import TedeeWebhookView

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.LOCK,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration setup."""

    coordinator = TedeeApiCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    home_assistant_token = entry.data.get(CONF_HOME_ASSISTANT_ACCESS_TOKEN, "")
    # Setup webhook if long lived access token
    if home_assistant_token != "":
        try:
            instance_url = get_url(hass)
            _LOGGER.debug("Registering webhook at %s/api/tedee/webhook", instance_url)
            hass.http.register_view(TedeeWebhookView(coordinator))
            headers: list[dict[str, str]] = [
                {"Authorization": f"Bearer {home_assistant_token}"}
            ]
            await coordinator.tedee_client.register_webhook(
                instance_url + "/api/tedee/webhook", headers
            )

        except NoURLAvailableError:
            _LOGGER.warning(
                "Could not register webhook, because no URL of Home Assistant could be found"
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # cleanup webhooks
    coordinator = hass.data[DOMAIN][entry.entry_id]
    try:
        await coordinator.tedee_client.delete_webhooks()
    except (TedeeClientException, TedeeAuthException) as ex:
        _LOGGER.warning("Error while deleting webhooks: %s", ex)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN] = {}

    return unload_ok
