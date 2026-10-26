"""The BUSY Bar integration."""

from functools import partial
import logging

from busylib import AsyncBusyBar
from busylib.exceptions import BusyBarAPIError, BusyBarError
from busylib.transports import AiohttpTransport

from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import BusyConfigEntry, BusyCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_create_client(
    hass: HomeAssistant, host: str, token: str | None = None
) -> AsyncBusyBar:
    """Create a client using Home Assistant's shared session."""
    transport = AiohttpTransport(async_get_clientsession(hass))
    return await hass.async_add_executor_job(
        partial(AsyncBusyBar, host, token=token, transport=transport, timeout=10)
    )


async def async_setup_entry(hass: HomeAssistant, entry: BusyConfigEntry) -> None:
    """Validate the token and start polling the bar."""
    client = await async_create_client(
        hass, entry.data[CONF_HOST], entry.data[CONF_TOKEN]
    )
    try:
        await client.access_tokens_list()
    except BusyBarError as err:
        await client.aclose()
        if isinstance(err, BusyBarAPIError) and err.status_code in (401, 403):
            raise ConfigEntryAuthFailed(
                "BUSY Bar token rejected; remove and add the bar"
            ) from err
        raise ConfigEntryNotReady("Cannot connect to BUSY Bar") from err
    coordinator = BusyCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await client.aclose()
        raise
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: BusyConfigEntry) -> None:
    """Unload sensors before closing their client."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.client.aclose()


async def async_remove_entry(hass: HomeAssistant, entry: BusyConfigEntry) -> None:
    """Revoke this entry's credential when it is removed."""
    try:
        async with await async_create_client(
            hass, entry.data[CONF_HOST], entry.data[CONF_TOKEN]
        ) as client:
            await client.access_tokens_revoke(entry.data[CONF_TOKEN][:8])
    except BusyBarError, OSError:
        _LOGGER.warning("Unable to revoke BUSY Bar access token; remove it on the bar")
