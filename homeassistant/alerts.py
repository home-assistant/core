"""Get alerts from 'alerts.home-assistant.io' and show as persistent notifications."""
from datetime import timedelta
import logging

import aiohttp

from homeassistant import core
from homeassistant.const import __version__ as current_version
from homeassistant.helpers import event
from homeassistant.loader import DATA_INTEGRATIONS

_LOGGER = logging.getLogger(__name__)

ALERT_URL = "https://alerts.home-assistant.io/alerts.json"
ALERT_NOTIF_ID_FORMAT = "alert_integration_" + "{}"

ALERTED_INTEGRATIONS = set()


async def async_setup_alerts(hass: core.HomeAssistant) -> None:
    """Retrieve the alerts and process them."""

    async def async_retrieve_alerts(*args):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(ALERT_URL) as response:
                    alert_data = await response.json()
            except Exception:
                hass.components.persistent_notification.async_create(
                    f"Could not retrieve latest alerts from {ALERT_URL}.",
                    "Error during alert data retrieval",
                )
                _LOGGER.error(f"Could not retrieve latest alerts from {ALERT_URL}")
                return

        for alert in alert_data:

            for integration in alert["integrations"]:
                integration_name = integration["package"]

                # If we already have a notification, do not raise again
                if integration_name in ALERTED_INTEGRATIONS:
                    continue

                # Check if integration is used / loaded
                if integration_name in hass.data.get(DATA_INTEGRATIONS):

                    # Check if alert is relevant based on min/max versions
                    relevant = True
                    if alert["homeassistant"]["package"] == "homeassistant":
                        min_version = alert["homeassistant"].get("min", "")
                        max_version = alert["homeassistant"].get("max", "")
                        relevant = check_version_relevant(
                            current_version, min_version, max_version
                        )

                    if relevant:
                        timestamp = alert.get("updated", alert.get("created", ""))

                        hass.components.persistent_notification.async_create(
                            alert["title"] + "<br/><br/>"
                            f"More details can be found in the [alert entry]({alert['alert_url']}).",
                            f"Integration alert: {hass.data.get(DATA_INTEGRATIONS)[integration_name].name}",
                            ALERT_NOTIF_ID_FORMAT.format(integration_name),
                            timestamp,
                        )

                        ALERTED_INTEGRATIONS.add(integration_name)

    # Initial run
    hass.async_create_task(async_retrieve_alerts())

    # Perform every hour
    event.async_track_time_interval(hass, async_retrieve_alerts, timedelta(seconds=10))


def check_version_relevant(current: str, min_version: str, max_version: str) -> bool:
    """Check if provided alert version matchtes the current HA version."""
    if min_version:
        if current < min_version:
            return False

    if max_version:
        if current > max_version:
            return False

    return True
