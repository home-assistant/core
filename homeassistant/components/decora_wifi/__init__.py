"""The decora_wifi component."""

import logging

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.person import Person

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    email = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    session = DecoraWiFiSession()

    # hass.data[DOMAIN] = AbodeSystem(abode, polling)
    hass.data[DOMAIN] = session

    # PR Need handle some config errors
    # except ConfigEntryError as ex:

    try:
        success = await hass.async_add_executor_job(
            lambda: session.login(email, password)
        )

        # If login failed, notify user.
        if success is None:
            msg = "Failed to log into myLeviton Services. Check credentials."
            _LOGGER.error(msg)
            # persistent_notification.create(
            #     hass, msg, title=NOTIFICATION_TITLE, notification_id=NOTIFICATION_ID
            # )
            # return

    except ValueError:
        _LOGGER.error("Failed to communicate with myLeviton Service")

    # Listen for the stop event and log out.
    def logout(event):
        """Log out..."""
        try:
            if session is not None:
                Person.logout(session)
        except ValueError:
            _LOGGER.error("Failed to log out of myLeviton Service")

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )

    # hass.bus.listen(EVENT_HOMEASSISTANT_STOP, logout)
    return True
