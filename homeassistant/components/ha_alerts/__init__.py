"""The Home Assistant Alerts integration."""
import asyncio
from datetime import timedelta
from distutils.version import StrictVersion
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import __short_version__ as current_version
from homeassistant.helpers import event
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ALERTS_URL = "https://alerts.home-assistant.io/alerts.json"

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

ALERT_SCHEMA = vol.Schema(
    {
        vol.Required("created"): cv.string,
        vol.Optional("updated"): cv.string,
        vol.Required("title"): cv.string,
        vol.Optional("alert_url"): cv.url,
        vol.Optional("integrations"): vol.All(
            cv.ensure_list, [{vol.Required("package"): cv.string}]
        ),
        vol.Optional("github_issue"): cv.url,
        vol.Optional("filename"): cv.string,
        vol.Required("homeassistant"): vol.Schema(
            {
                vol.Required("package"): cv.string,
                vol.Optional("min", default="0.0"): cv.string,
            }
        ),
    }
)

ALERTS_SCHEMA = vol.Schema(vol.All(cv.ensure_list, [ALERT_SCHEMA]))


async def async_setup(hass, config):
    """Set up the Home Assistant Alerts integration."""

    async def check_new_alerts(now):
        """Check if there are new alerts."""
        alerts = await get_alerts(hass)

        if alerts is None:
            return

        _LOGGER.debug("relevant alerts: %s", len(alerts))

        for alert in alerts:
            alert_text = (
                f"More details: {alert['alert_url']} <br /> Created: {alert['created']}"
            )
            hass.components.persistent_notification.async_create(
                alert_text,
                title=alert["title"],
                notification_id=f"alert_{alert['integrations'][0]['package']}",
            )

    # Update daily, start 5 minutes after startup
    _dt = dt_util.utcnow() + timedelta(minutes=5)
    event.async_track_utc_time_change(
        hass, check_new_alerts, hour=_dt.hour, minute=_dt.minute, second=_dt.second
    )

    return True


async def get_alerts(hass):
    """Get the Home Assistant Alerts."""
    session = async_get_clientsession(hass)
    try:
        with async_timeout.timeout(5):
            response = await session.get(ALERTS_URL)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Could not contact Home Assistant Alerts to check for alerts")
        return None

    try:
        alerts = await response.json()
        _LOGGER.debug("Currently present alerts: %s", len(alerts))
    except ValueError:
        _LOGGER.error("Received invalid JSON from Home Assistant Alerts")
        return None

    try:
        alerts = ALERTS_SCHEMA(alerts)
    except vol.Invalid:
        _LOGGER.error("Got unexpected response: %s", alerts)
        return None

    present_components = [
        integration.split(".", 1)[-1] for integration in list(hass.config.components)
    ]

    relevant_alerts = []

    for alert in alerts:
        min_version = alert["homeassistant"]["min"]

        if StrictVersion(min_version) > StrictVersion(current_version):
            _LOGGER.debug("Running version is not affected: %s", alert["title"])
            continue

        for integration in alert["integrations"]:
            if integration["package"] in present_components:
                relevant_alerts.append(alert)

    return relevant_alerts
