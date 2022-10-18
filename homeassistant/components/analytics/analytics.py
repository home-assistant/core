"""Analytics helper class for the analytics integration."""
import asyncio
from typing import Any
import uuid

import aiohttp
import async_timeout

from homeassistant.components import hassio
from homeassistant.components.api import ATTR_INSTALLATION_TYPE
from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.energy import (
    DOMAIN as ENERGY_DOMAIN,
    is_configured as energy_is_configured,
)
from homeassistant.const import ATTR_DOMAIN, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.loader import IntegrationNotFound, async_get_integrations
from homeassistant.setup import async_get_loaded_integrations

from .const import (
    ANALYTICS_ENDPOINT_URL,
    ANALYTICS_ENDPOINT_URL_DEV,
    ATTR_ADDON_COUNT,
    ATTR_ADDONS,
    ATTR_ARCH,
    ATTR_AUTO_UPDATE,
    ATTR_AUTOMATION_COUNT,
    ATTR_BASE,
    ATTR_BOARD,
    ATTR_CERTIFICATE,
    ATTR_CONFIGURED,
    ATTR_CUSTOM_INTEGRATIONS,
    ATTR_DIAGNOSTICS,
    ATTR_ENERGY,
    ATTR_HEALTHY,
    ATTR_INTEGRATION_COUNT,
    ATTR_INTEGRATIONS,
    ATTR_ONBOARDED,
    ATTR_OPERATING_SYSTEM,
    ATTR_PREFERENCES,
    ATTR_PROTECTED,
    ATTR_SLUG,
    ATTR_STATE_COUNT,
    ATTR_STATISTICS,
    ATTR_SUPERVISOR,
    ATTR_SUPPORTED,
    ATTR_USAGE,
    ATTR_USER_COUNT,
    ATTR_UUID,
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
        self._data: dict[str, Any] = {
            ATTR_PREFERENCES: {},
            ATTR_ONBOARDED: False,
            ATTR_UUID: None,
        }
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)

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
    def uuid(self) -> bool:
        """Return the uuid for the analytics integration."""
        return self._data[ATTR_UUID]

    @property
    def endpoint(self) -> str:
        """Return the endpoint that will receive the payload."""
        if HA_VERSION.endswith("0.dev0"):
            # dev installations will contact the dev analytics environment
            return ANALYTICS_ENDPOINT_URL_DEV
        return ANALYTICS_ENDPOINT_URL

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
        operating_system_info = {}

        if not self.onboarded or not self.preferences.get(ATTR_BASE, False):
            LOGGER.debug("Nothing to submit")
            return

        if self._data.get(ATTR_UUID) is None:
            self._data[ATTR_UUID] = uuid.uuid4().hex
            await self._store.async_save(self._data)

        if self.supervisor:
            supervisor_info = hassio.get_supervisor_info(self.hass)
            operating_system_info = hassio.get_os_info(self.hass)

        system_info = await async_get_system_info(self.hass)
        integrations = []
        custom_integrations = []
        addons = []
        payload: dict = {
            ATTR_UUID: self.uuid,
            ATTR_VERSION: HA_VERSION,
            ATTR_INSTALLATION_TYPE: system_info[ATTR_INSTALLATION_TYPE],
        }

        if supervisor_info is not None:
            payload[ATTR_SUPERVISOR] = {
                ATTR_HEALTHY: supervisor_info[ATTR_HEALTHY],
                ATTR_SUPPORTED: supervisor_info[ATTR_SUPPORTED],
                ATTR_ARCH: supervisor_info[ATTR_ARCH],
            }

        if operating_system_info.get(ATTR_BOARD) is not None:
            payload[ATTR_OPERATING_SYSTEM] = {
                ATTR_BOARD: operating_system_info[ATTR_BOARD],
                ATTR_VERSION: operating_system_info[ATTR_VERSION],
            }

        if self.preferences.get(ATTR_USAGE, False) or self.preferences.get(
            ATTR_STATISTICS, False
        ):
            domains = async_get_loaded_integrations(self.hass)
            configured_integrations = await async_get_integrations(self.hass, domains)
            for integration in configured_integrations.values():
                if isinstance(integration, IntegrationNotFound):
                    continue

                if isinstance(integration, BaseException):
                    raise integration

                if integration.disabled:
                    continue

                if not integration.is_built_in:
                    custom_integrations.append(
                        {
                            ATTR_DOMAIN: integration.domain,
                            ATTR_VERSION: integration.version,
                        }
                    )
                    continue

                integrations.append(integration.domain)

            if supervisor_info is not None:
                installed_addons = await asyncio.gather(
                    *(
                        hassio.async_get_addon_info(self.hass, addon[ATTR_SLUG])
                        for addon in supervisor_info[ATTR_ADDONS]
                    )
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
            payload[ATTR_CERTIFICATE] = self.hass.http.ssl_certificate is not None
            payload[ATTR_INTEGRATIONS] = integrations
            payload[ATTR_CUSTOM_INTEGRATIONS] = custom_integrations
            if supervisor_info is not None:
                payload[ATTR_ADDONS] = addons

            if ENERGY_DOMAIN in integrations:
                payload[ATTR_ENERGY] = {
                    ATTR_CONFIGURED: await energy_is_configured(self.hass)
                }

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
            async with async_timeout.timeout(30):
                response = await self.session.post(self.endpoint, json=payload)
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
                        "Sending analytics failed with statuscode %s from %s",
                        response.status,
                        self.endpoint,
                    )
        except asyncio.TimeoutError:
            LOGGER.error("Timeout sending analytics to %s", ANALYTICS_ENDPOINT_URL)
        except aiohttp.ClientError as err:
            LOGGER.error(
                "Error sending analytics to %s: %r", ANALYTICS_ENDPOINT_URL, err
            )
