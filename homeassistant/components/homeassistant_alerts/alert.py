"""Create issues based on active alerts."""
from __future__ import annotations

import dataclasses
from datetime import timedelta
import logging

import aiohttp
from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.components.resolution_center import (
    async_create_issue,
    async_delete_issue,
)
from homeassistant.components.resolution_center.models import IssueSeverity
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class IntegrationAlert:
    """Issue Registry Entry."""

    integration: str
    issue_id: str
    learn_more_url: str | None


async def async_setup(hass: HomeAssistant) -> None:
    """Set up alerts."""
    hass.data[DOMAIN]["alerts"] = set()
    ha_version = AwesomeVersion(
        __version__,
        ensure_strategy=AwesomeVersionStrategy.CALVER,
        find_first_match=False,
    )

    async def async_update_data() -> dict[str, IntegrationAlert]:
        """Fetch data from API endpoint."""
        response = await session.request(
            "get",
            "https://alerts.home-assistant.io/alerts.json",
            timeout=aiohttp.ClientTimeout(total=10),
        )
        alerts = await response.json()

        result = {}

        for alert in alerts:
            if "homeassistant" in alert:
                if "min" in alert["homeassistant"]:
                    min_version = AwesomeVersion(
                        alert["homeassistant"]["min"],
                        find_first_match=False,
                    )
                    if ha_version < min_version:
                        continue
                if "max" in alert["homeassistant"]:
                    max_version = AwesomeVersion(
                        alert["homeassistant"]["max"],
                        find_first_match=False,
                    )
                    if ha_version >= max_version:
                        continue
            if "alert_url" not in alert or "integrations" not in alert:
                continue
            for integration in alert["integrations"]:
                if "package" not in integration:
                    continue
                issue_id = f"{alert['filename']}_{integration['package']}"
                result[issue_id] = IntegrationAlert(
                    integration["package"], issue_id, alert["alert_url"]
                )

        return result

    @callback
    def async_update_alerts() -> None:
        if not coordinator.last_update_success:
            return

        old_alerts = hass.data[DOMAIN]["alerts"]

        active_alerts = set()

        for issue_id, alert in coordinator.data.items():
            if alert.integration not in hass.config.components:
                continue
            async_create_issue(
                hass,
                "homeassistant_alerts",
                issue_id,
                is_fixable=False,
                learn_more_url=alert.learn_more_url,
                severity=IssueSeverity.WARNING,
                translation_key="alert",
                translation_placeholders={"integration": alert.integration},
            )
            active_alerts.add(issue_id)

        inactive_alerts = old_alerts - active_alerts
        for issue_id in inactive_alerts:
            async_delete_issue(hass, "homeassistant_alerts", issue_id)

        hass.data[DOMAIN]["alerts"] = active_alerts

    session = async_get_clientsession(hass)
    coordinator = DataUpdateCoordinator[dict[str, IntegrationAlert]](
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="homeassistant_alerts",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(minutes=60),
    )
    coordinator.async_add_listener(async_update_alerts)
    await coordinator.async_refresh()
