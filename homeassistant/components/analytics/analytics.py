"""Analytics helper class for the analytics integration."""
import asyncio
from typing import List

import aiohttp
import async_timeout

from homeassistant.components import hassio
from homeassistant.components.api import ATTR_INSTALLATION_TYPE
from homeassistant.components.automation.const import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.loader import async_get_integration

from .const import (
    ANALYTICS_ENDPOINT_URL,
    ATTR_ADDON_COUNT,
    ATTR_ADDONS,
    ATTR_AUTO_UPDATE,
    ATTR_AUTOMATION_COUNT,
    ATTR_DIAGNOSTICS,
    ATTR_HEALTHY,
    ATTR_HUUID,
    ATTR_INTEGRATION_COUNT,
    ATTR_INTEGRATIONS,
    ATTR_ONBOARDED,
    ATTR_PREFERENCES,
    ATTR_PROTECTED,
    ATTR_SLUG,
    ATTR_STATE_COUNT,
    ATTR_SUPERVISOR,
    ATTR_SUPPORTED,
    ATTR_USER_COUNT,
    ATTR_VERSION,
    INGORED_DOMAINS,
    LOGGER,
    STORAGE_KEY,
    STORAGE_VERSION,
    AnalyticsPreference,
)


class Analytics:
    """Analytics helper class for the analytics integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Analytics class."""
        self.hass: HomeAssistant = hass
        self.session = async_get_clientsession(hass)
        self._data = {}
        self._store: Store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @property
    def preferences(self) -> List[AnalyticsPreference]:
        """Return the current active preferences."""
        return self._data.get(ATTR_PREFERENCES, [])

    @property
    def onboarded(self) -> bool:
        """Return bool if the user has made a choice."""
        return self._data.get(ATTR_ONBOARDED, False)

    @property
    def supervisor(self) -> bool:
        """Return bool if a supervisor is present."""
        return hassio.DOMAIN in self.hass.data

    async def load(self) -> None:
        """Load preferences."""
        self._data = await self._store.async_load() or {}
        if self.supervisor:
            supervisor_info = hassio.get_supervisor_info(self.hass)
            if not self.onboarded:
                # User have not configured analytics, get this setting from the supervisor
                if (
                    supervisor_info[ATTR_DIAGNOSTICS]
                    and AnalyticsPreference.DIAGNOSTICS not in self.preferences
                ):
                    self._data.setdefault(ATTR_PREFERENCES, []).append(ATTR_DIAGNOSTICS)
                elif (
                    not supervisor_info[ATTR_DIAGNOSTICS]
                    and AnalyticsPreference.DIAGNOSTICS in self.preferences
                ):
                    self._data.setdefault(ATTR_PREFERENCES, []).remove(ATTR_DIAGNOSTICS)

    async def save_preferences(self, preferences: List[AnalyticsPreference]) -> None:
        """Save preferences."""
        self._data[ATTR_PREFERENCES] = preferences
        self._data[ATTR_ONBOARDED] = True
        await self._store.async_save(self._data)

        if self.supervisor:
            await hassio.async_update_diagnostics(
                self.hass, AnalyticsPreference.DIAGNOSTICS in self.preferences
            )

    async def send_analytics(self, _=None) -> None:
        """Send analytics."""
        supervisor_info = None

        if not self.onboarded or AnalyticsPreference.BASE not in self.preferences:
            LOGGER.debug("Nothing to submit")
            return

        huuid = await self.hass.helpers.instance_id.async_get()

        if self.supervisor:
            supervisor_info = hassio.get_supervisor_info(self.hass)

        system_info = await async_get_system_info(self.hass)
        integrations = []
        addons = []
        payload: dict = {
            ATTR_HUUID: huuid,
            ATTR_VERSION: HA_VERSION,
            ATTR_INSTALLATION_TYPE: system_info[ATTR_INSTALLATION_TYPE],
        }

        if supervisor_info is not None:
            payload[ATTR_SUPERVISOR] = {
                ATTR_HEALTHY: supervisor_info[ATTR_HEALTHY],
                ATTR_SUPPORTED: supervisor_info[ATTR_SUPPORTED],
            }

        if (
            AnalyticsPreference.USAGE in self.preferences
            or AnalyticsPreference.STATISTICS in self.preferences
        ):
            configured_integrations = await asyncio.gather(
                *[
                    async_get_integration(self.hass, domain)
                    for domain in self.hass.config.components
                    # Filter out platforms.
                    if "." not in domain
                ]
            )

            for integration in configured_integrations:
                if (
                    integration.disabled
                    or integration.domain in INGORED_DOMAINS
                    or not integration.is_built_in
                ):
                    continue

                integrations.append(integration.domain)

            if supervisor_info is not None:
                installed_addons = await asyncio.gather(
                    *[
                        hassio.async_get_addon_info(self.hass, addon[ATTR_SLUG])
                        for addon in supervisor_info[ATTR_ADDONS]
                    ]
                )
                for addon in installed_addons:
                    addons.append(
                        {
                            ATTR_SLUG: addon[ATTR_SLUG],
                            ATTR_PROTECTED: addon[ATTR_PROTECTED],
                            ATTR_VERSION: addon[ATTR_VERSION],
                            ATTR_AUTO_UPDATE: addon[ATTR_AUTO_UPDATE],
                        }
                    )

        if AnalyticsPreference.USAGE in self.preferences:
            payload[ATTR_INTEGRATIONS] = integrations
            if supervisor_info is not None:
                payload[ATTR_ADDONS] = addons

        if AnalyticsPreference.STATISTICS in self.preferences:
            payload[ATTR_STATE_COUNT] = len(self.hass.states.async_all())
            payload[ATTR_AUTOMATION_COUNT] = len(
                self.hass.states.async_all(AUTOMATION_DOMAIN)
            )
            payload[ATTR_INTEGRATION_COUNT] = len(integrations)
            if supervisor_info is not None:
                payload[ATTR_ADDON_COUNT] = len(addons)
            payload[ATTR_USER_COUNT] = len(
                [
                    user
                    for user in await self.hass.auth.async_get_users()
                    if not user.system_generated
                ]
            )

        try:
            with async_timeout.timeout(30):
                response = await self.session.post(ANALYTICS_ENDPOINT_URL, json=payload)
                if response.status == 200:
                    LOGGER.info(
                        (
                            "Submitted analytics to Home Assistant servers. "
                            "Information submitted includes %s"
                        ),
                        payload,
                    )
                else:
                    LOGGER.warning(
                        "Sending analytics failed with statuscode %s", response.status
                    )
        except asyncio.TimeoutError:
            LOGGER.error("Timeout sending analytics to %s", ANALYTICS_ENDPOINT_URL)
        except aiohttp.ClientError as err:
            LOGGER.error(
                "Error sending analytics to %s: %r", ANALYTICS_ENDPOINT_URL, err
            )
