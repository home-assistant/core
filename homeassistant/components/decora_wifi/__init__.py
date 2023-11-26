"""The decora_wifi component."""

import logging

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.person import Person

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, Event
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    session = DecoraWiFiSession()
    user = await hass.async_add_executor_job(lambda: session.login(username, password))
    if not user:
        raise ConfigEntryAuthFailed("invalid authentication")

    hass.data[DOMAIN][entry.entry_id] = session

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )

    # Listen for the stop event and log out.
    def logout(event: Event) -> None:
        try:
            if session is not None:
                Person.logout(session)
        except ValueError:
            _LOGGER.error("Failed to log out of myLeviton Service")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.pop(DOMAIN)
    return unload_ok
