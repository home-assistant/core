"""DataUpdateCoordinator for the Homeassistant Analytics integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import time
from typing import TYPE_CHECKING, override

from python_homeassistant_analytics import (
    CustomIntegration,
    HomeassistantAnalyticsClient,
    HomeassistantAnalyticsConnectionError,
    HomeassistantAnalyticsNotModifiedError,
)
from python_homeassistant_analytics.models import Addon

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_TRACKED_APPS,
    CONF_TRACKED_CUSTOM_INTEGRATIONS,
    CONF_TRACKED_INTEGRATIONS,
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from . import AnalyticsInsightsConfigEntry


@dataclass(frozen=True)
class AnalyticsData:
    """Analytics data class."""

    active_installations: int
    reports_integrations: int
    apps: dict[str, int]
    core_integrations: dict[str, int]
    custom_integrations: dict[str, int]


class HomeassistantAnalyticsDataUpdateCoordinator(DataUpdateCoordinator[AnalyticsData]):
    """A Homeassistant Analytics Data Update Coordinator."""

    config_entry: AnalyticsInsightsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AnalyticsInsightsConfigEntry,
        client: HomeassistantAnalyticsClient,
    ) -> None:
        """Initialize the Homeassistant Analytics data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
        )
        self._client = client
        self._tracked_apps = self.config_entry.options.get(CONF_TRACKED_APPS, [])
        self._tracked_integrations = self.config_entry.options[
            CONF_TRACKED_INTEGRATIONS
        ]
        self._tracked_custom_integrations = self.config_entry.options[
            CONF_TRACKED_CUSTOM_INTEGRATIONS
        ]

    async def _async_fetch[_T](
        self, endpoint: str, fetch: Callable[[], Awaitable[_T]]
    ) -> _T:
        """Fetch one endpoint, logging timing, ETag state and any failure."""
        LOGGER.debug(
            "Fetching %s (stored ETags: %s)",
            endpoint,
            self._client._etags,  # noqa: SLF001
        )
        start = time.monotonic()
        try:
            result = await fetch()
        except HomeassistantAnalyticsNotModifiedError:
            LOGGER.debug(
                "%s not modified (304) after %.3fs",
                endpoint,
                time.monotonic() - start,
            )
            raise
        except Exception as err:
            LOGGER.warning(
                "%s failed after %.3fs with %s: %s",
                endpoint,
                time.monotonic() - start,
                type(err).__name__,
                str(err.args)[:2000],
                exc_info=True,
            )
            raise
        LOGGER.debug(
            "%s fetched in %.3fs: %s",
            endpoint,
            time.monotonic() - start,
            f"{len(result)} entries" if isinstance(result, dict) else type(result),
        )
        return result

    @override
    async def _async_update_data(self) -> AnalyticsData:
        LOGGER.debug(
            "Starting update (last_update_success: %s, has data: %s)",
            self.last_update_success,
            self.data is not None,
        )
        try:
            apps_data = await self._async_fetch(
                "addons.json", self._client.get_addons
            )  # Still add method name. Needs library update
            data = await self._async_fetch(
                "current_data.json", self._client.get_current_analytics
            )
            custom_data = await self._async_fetch(
                "custom_integrations.json", self._client.get_custom_integrations
            )
        except HomeassistantAnalyticsConnectionError as err:
            LOGGER.warning("Connection error, raising UpdateFailed: %s", err)
            raise UpdateFailed(
                "Error communicating with Homeassistant Analytics"
            ) from err
        except HomeassistantAnalyticsNotModifiedError:
            LOGGER.debug(
                "Not modified, keeping previous data (has data: %s)",
                self.data is not None,
            )
            return self.data
        except Exception as err:
            LOGGER.warning(
                "Unhandled %s escaping the coordinator, entities will be "
                "unavailable until the next update in %s",
                type(err).__name__,
                self.update_interval,
            )
            raise
        apps = {app: get_app_value(apps_data, app) for app in self._tracked_apps}
        core_integrations = {
            integration: data.integrations.get(integration, 0)
            for integration in self._tracked_integrations
        }
        custom_integrations = {
            integration: get_custom_integration_value(custom_data, integration)
            for integration in self._tracked_custom_integrations
        }
        LOGGER.debug(
            "Update parsed: active_installations=%s, reports_integrations=%s, "
            "apps=%s, core_integrations=%s, custom_integrations=%s",
            data.active_installations,
            data.reports_integrations,
            apps,
            core_integrations,
            custom_integrations,
        )
        return AnalyticsData(
            data.active_installations,
            data.reports_integrations,
            apps,
            core_integrations,
            custom_integrations,
        )


def get_app_value(data: dict[str, Addon], name_slug: str) -> int:
    """Get app value."""
    if name_slug in data:
        return data[name_slug].total
    return 0


def get_custom_integration_value(
    data: dict[str, CustomIntegration], domain: str
) -> int:
    """Get custom integration value."""
    if domain in data:
        return data[domain].total
    return 0
