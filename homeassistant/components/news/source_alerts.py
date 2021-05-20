"""Alerts source for the news integration."""
import asyncio
from typing import TYPE_CHECKING, Set

from awesomeversion import AwesomeVersion

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_get_loaded_integrations

from .const import (
    ATTR_ALERT_URL,
    ATTR_CREATED,
    ATTR_HOMEASSISTANT,
    ATTR_INTEGRATIONS,
    ATTR_MAX,
    ATTR_MIN,
    ATTR_PACKAGE,
    ATTR_TITLE,
    ATTR_URL,
    NewsSource,
)

if TYPE_CHECKING:
    from .manager import NewsManager

SOURCE_URL = "https://alerts.home-assistant.io/alerts.json"


async def source_update_alerts(hass: HomeAssistant, manager: "NewsManager") -> None:
    """Update the alerts source."""
    if (
        alerts := await manager.get_external_source_data(SOURCE_URL, NewsSource.ALERTS)
    ) is None:
        return

    new_alerts = set()
    old_alerts = manager.source_events(NewsSource.ALERTS)
    loaded_integrations = async_get_loaded_integrations(hass)

    async def handle_new_alert(alert):
        """Handle new alert."""
        if not _alert_has_impact(alert, loaded_integrations):
            return

        event_key = await manager.register_event(
            source=NewsSource.ALERTS,
            id=alert[ATTR_CREATED],
            event_data={
                ATTR_TITLE: alert[ATTR_TITLE],
                ATTR_URL: alert[ATTR_ALERT_URL],
            },
        )
        new_alerts.add(event_key)

    await asyncio.gather(
        *[
            handle_new_alert(alert)
            for alert in alerts
            if _alert_has_impact(alert, loaded_integrations)
        ]
    )

    await asyncio.gather(
        *[
            manager.dismiss_event(event)
            for event in old_alerts
            if event not in new_alerts
        ]
    )


def _alert_has_impact(alert: dict, configured_integrations: Set[str]) -> bool:
    """Check if an alert has impact."""
    if (
        ATTR_MIN in alert[ATTR_HOMEASSISTANT]
        and AwesomeVersion(alert[ATTR_HOMEASSISTANT][ATTR_MIN]) > HA_VERSION
    ):
        return False
    if (
        ATTR_MAX in alert[ATTR_HOMEASSISTANT]
        and AwesomeVersion(alert[ATTR_HOMEASSISTANT][ATTR_MAX]) < HA_VERSION
    ):
        return False

    if not any(
        [
            integration
            for integration in [
                integration[ATTR_PACKAGE] for integration in alert[ATTR_INTEGRATIONS]
            ]
            if integration in configured_integrations
        ]
    ):
        return False

    return True
