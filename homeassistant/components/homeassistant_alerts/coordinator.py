"""Coordinator for the Home Assistant alerts integration."""

import dataclasses
import logging

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.components.hassio import get_supervisor_info, is_hassio
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, REQUEST_TIMEOUT, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True, frozen=True)
class IntegrationAlert:
    """Issue Registry Entry."""

    alert_id: str
    integration: str
    filename: str
    date_updated: str | None

    @property
    def issue_id(self) -> str:
        """Return the issue id."""
        return f"{self.filename}_{self.integration}"


class AlertUpdateCoordinator(DataUpdateCoordinator[dict[str, IntegrationAlert]]):
    """Data fetcher for HA Alerts."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.ha_version = AwesomeVersion(
            __version__,
            ensure_strategy=AwesomeVersionStrategy.CALVER,
        )
        self.supervisor = is_hassio(self.hass)

    async def _async_update_data(self) -> dict[str, IntegrationAlert]:
        response = await async_get_clientsession(self.hass).get(
            "https://alerts.home-assistant.io/alerts.json",
            timeout=REQUEST_TIMEOUT,
        )
        alerts = await response.json()

        result = {}

        for alert in alerts:
            if "integrations" not in alert:
                continue

            if "homeassistant" in alert:
                if "affected_from_version" in alert["homeassistant"]:
                    affected_from_version = AwesomeVersion(
                        alert["homeassistant"]["affected_from_version"],
                    )
                    if self.ha_version < affected_from_version:
                        continue
                if "resolved_in_version" in alert["homeassistant"]:
                    resolved_in_version = AwesomeVersion(
                        alert["homeassistant"]["resolved_in_version"],
                    )
                    if self.ha_version >= resolved_in_version:
                        continue

            if self.supervisor and "supervisor" in alert:
                if (supervisor_info := get_supervisor_info(self.hass)) is None:
                    continue

                if "affected_from_version" in alert["supervisor"]:
                    affected_from_version = AwesomeVersion(
                        alert["supervisor"]["affected_from_version"],
                    )
                    if supervisor_info["version"] < affected_from_version:
                        continue
                if "resolved_in_version" in alert["supervisor"]:
                    resolved_in_version = AwesomeVersion(
                        alert["supervisor"]["resolved_in_version"],
                    )
                    if supervisor_info["version"] >= resolved_in_version:
                        continue

            for integration in alert["integrations"]:
                if "package" not in integration:
                    continue

                if integration["package"] not in self.hass.config.components:
                    continue

                integration_alert = IntegrationAlert(
                    alert_id=alert["id"],
                    integration=integration["package"],
                    filename=alert["filename"],
                    date_updated=alert.get("updated"),
                )

                result[integration_alert.issue_id] = integration_alert

        return result
