"""Analytics helper class for the analytics integration."""
import asyncio

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
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.setup import async_get_loaded_integrations

from .const import (
    ANALYTICS_ENDPOINT_URL,
    ATTR_ADDON_COUNT,
    ATTR_ADDONS,
    ATTR_AUTO_UPDATE,
    ATTR_AUTOMATION_COUNT,
    ATTR_BASE,
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
    ATTR_STATISTICS,
    ATTR_SUPERVISOR,
    ATTR_SUPPORTED,
    ATTR_USAGE,
    ATTR_USER_COUNT,
    ATTR_VERSION,
    LOGGER,
    PREFERENCE_SCHEMA,
    STORAGE_KEY,
    STORAGE_VERSION,
)


class Analytics:
    """Analytics helper class for the analytics integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Analytics class."""
        self.hass: HomeAssistant = hass
        self.session = async_get_clientsession(hass)
        self._data = {ATTR_PREFERENCES: {}, ATTR_ONBOARDED: False}
        self._store: Store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @property
    def preferences(self) -> dict:
        """Return the current active preferences."""
        preferences = self._data[ATTR_PREFERENCES]
        return {
            ATTR_BASE: preferences.get(ATTR_BASE, False),
            ATTR_DIAGNOSTICS: preferences.get(ATTR_DIAGNOSTICS, False),
            ATTR_USAGE: preferences.get(ATTR_USAGE, False),
            ATTR_STATISTICS: preferences.get(ATTR_STATISTICS, False),
        }

    @property
    def onboarded(self) -> bool:
        """Return bool if the user has made a choice."""
        return self._data[ATTR_ONBOARDED]

    @property
    def supervisor(self) -> bool:
        """Return bool if a supervisor is present."""
        return hassio.is_hassio(self.hass)

    async def load(self) -> None:
        """Load preferences."""
        stored = await self._store.async_load()
        if stored:
            self._data = stored
        if self.supervisor:
            supervisor_info = hassio.get_supervisor_info(self.hass)
            if not self.onboarded:
                # User have not configured analytics, get this setting from the supervisor
                if supervisor_info[ATTR_DIAGNOSTICS] and not self.preferences.get(
                    ATTR_DIAGNOSTICS, False
                ):
                    self._data[ATTR_PREFERENCES][ATTR_DIAGNOSTICS] = True
                elif not supervisor_info[ATTR_DIAGNOSTICS] and self.preferences.get(
                    ATTR_DIAGNOSTICS, False
                ):
                    self._data[ATTR_PREFERENCES][ATTR_DIAGNOSTICS] = False

    async def save_preferences(self, preferences: dict) -> None:
        """Save preferences."""
        preferences = PREFERENCE_SCHEMA(preferences)
        self._data[ATTR_PREFERENCES].update(preferences)
        self._data[ATTR_ONBOARDED] = True
        await self._store.async_save(self._data)

        if self.supervisor:
            await hassio.async_update_diagnostics(
                self.hass, self.preferences.get(ATTR_DIAGNOSTICS, False)
            )

    async def send_analytics(self, _=None) -> None:
        """Send analytics."""
        supervisor_info = None

        if not self.onboarded or not self.preferences.get(ATTR_BASE, False):
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

        if self.preferences.get(ATTR_USAGE, False) or self.preferences.get(
            ATTR_STATISTICS, False
        ):
            configured_integrations = await asyncio.gather(
                *[
                    async_get_integration(self.hass, domain)
                    for domain in async_get_loaded_integrations(self.hass)
                ],
                return_exceptions=True,
            )

            for integration in configured_integrations:
                if isinstance(integration, IntegrationNotFound):
                    continue

                if isinstance(integration, BaseException):
                    raise integration

                if integration.disabled or not integration.is_built_in:
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

        if self.preferences.get(ATTR_USAGE, False):
            payload[ATTR_INTEGRATIONS] = integrations
            if supervisor_info is not None:
                payload[ATTR_ADDONS] = addons

        if self.preferences.get(ATTR_STATISTICS, False):
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
