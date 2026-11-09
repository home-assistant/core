"""Install and start the Voice app through the Supervisor."""

import asyncio
from dataclasses import dataclass

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import Discovery

from homeassistant.components.hassio import AddonManager, get_supervisor_client
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import APP_NAME, APP_SLUG, DISCOVERY_TIMEOUT, DOMAIN, LOGGER

DATA_APP_MANAGER = f"{DOMAIN}_app_manager"


@dataclass(frozen=True)
class DiscoveredApp:
    """The app as discovered through the Supervisor."""

    uuid: str
    host: str
    port: int

    @staticmethod
    def from_discovery(discovery: Discovery) -> DiscoveredApp:
        """Read a discovery message from the app."""
        return DiscoveredApp(
            uuid=discovery.uuid.hex,
            host=discovery.config["host"],
            port=discovery.config["port"],
        )


@singleton(DATA_APP_MANAGER)
@callback
def get_app_manager(hass: HomeAssistant) -> AddonManager:
    """Get the app manager."""
    return AddonManager(hass, LOGGER, APP_NAME, APP_SLUG)


async def async_get_discovery(hass: HomeAssistant) -> DiscoveredApp | None:
    """Return the app's discovery message, if there is one."""
    client = get_supervisor_client(hass)
    try:
        messages = await client.discovery.list()
    except SupervisorError as err:
        LOGGER.debug("Cannot read discovery messages: %s", err)
        return None

    discovery = next((m for m in messages if m.addon == APP_SLUG), None)
    return None if discovery is None else DiscoveredApp.from_discovery(discovery)


async def async_wait_for_discovery(hass: HomeAssistant) -> DiscoveredApp | None:
    """Wait for a started app to send its discovery message."""
    try:
        async with asyncio.timeout(DISCOVERY_TIMEOUT):
            while True:
                if (app := await async_get_discovery(hass)) is not None:
                    return app
                await asyncio.sleep(1)
    except TimeoutError:
        LOGGER.warning(
            "%s did not announce itself within %s seconds",
            APP_NAME,
            DISCOVERY_TIMEOUT,
        )
        return None
