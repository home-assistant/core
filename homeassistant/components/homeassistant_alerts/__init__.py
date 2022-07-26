"""The Home Assistant alerts integration."""
from __future__ import annotations

import dataclasses
from datetime import timedelta
import logging

import aiohttp
from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.components.repairs import async_create_issue, async_delete_issue
from homeassistant.components.repairs.models import IssueSeverity
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

DOMAIN = "homeassistant_alerts"
UPDATE_INTERVAL = timedelta(hours=3)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up alerts."""
    last_alerts = set()

    @callback
    def async_update_alerts() -> None:
        if not coordinator.last_update_success:
            return

        nonlocal last_alerts

        active_alerts = set()

        for issue_id, alert in coordinator.data.items():
            if alert.integration not in hass.config.components:
                continue
            async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                learn_more_url=alert.learn_more_url,
                severity=IssueSeverity.WARNING,
                translation_key="alert",
                translation_placeholders={"integration": alert.integration},
            )
            active_alerts.add(issue_id)

        inactive_alerts = last_alerts - active_alerts
        for issue_id in inactive_alerts:
            async_delete_issue(hass, DOMAIN, issue_id)

        last_alerts = active_alerts

    coordinator = AlertUpdateCoordinator(hass)
    coordinator.async_add_listener(async_update_alerts)
    await coordinator.async_refresh()

    return True


@dataclasses.dataclass(frozen=True)
class IntegrationAlert:
    """Issue Registry Entry."""

    integration: str
    issue_id: str
    learn_more_url: str | None


class AlertUpdateCoordinator(DataUpdateCoordinator[dict[str, IntegrationAlert]]):
    """Data fetcher for HA Alerts."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.ha_version = AwesomeVersion(
            __version__,
            ensure_strategy=AwesomeVersionStrategy.CALVER,
            find_first_match=False,
        )

    async def _async_update_data(self) -> dict[str, IntegrationAlert]:
        response = await async_get_clientsession(self.hass).request(
            "get",
            "https://alerts.home-assistant.io/alerts.json",
            timeout=aiohttp.ClientTimeout(total=10),
        )
        alerts = await response.json()

        result = {}

        for alert in alerts:
            if "alert_url" not in alert or "integrations" not in alert:
                continue

            if "homeassistant" in alert:
                if "affected_from_version" in alert["homeassistant"]:
                    affected_from_version = AwesomeVersion(
                        alert["homeassistant"]["affected_from_version"],
                        find_first_match=False,
                    )
                    if self.ha_version < affected_from_version:
                        continue
                if "resolved_in_version" in alert["homeassistant"]:
                    resolved_in_version = AwesomeVersion(
                        alert["homeassistant"]["resolved_in_version"],
                        find_first_match=False,
                    )
                    if self.ha_version >= resolved_in_version:
                        continue

            for integration in alert["integrations"]:
                if "package" not in integration:
                    continue
                issue_id = f"{alert['filename']}_{integration['package']}"
                result[issue_id] = IntegrationAlert(
                    integration["package"], issue_id, alert["alert_url"]
                )

        return result
