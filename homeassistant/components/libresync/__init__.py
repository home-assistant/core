"""The LibreSync integration."""

import asyncio
from collections.abc import Callable

from aiolibresync import (
    DeviceState,
    LibreSyncClient,
    LssdpInfo,
    NotConnectedError,
    async_query_lssdp,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONNECT_TIMEOUT, DOMAIN, MANUFACTURER, UNSUPPORTED_MODULES

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type LibreSyncConfigEntry = ConfigEntry[LibreSyncClient]


def unsupported_module(info: LssdpInfo | None) -> str | None:
    """Return the module LSSDP named if this integration cannot drive it.

    A hub that did not answer on LSSDP is not refused: None means unknown.
    """
    if info is not None and info.module in UNSUPPORTED_MODULES:
        return info.module
    return None


async def async_setup_entry(hass: HomeAssistant, entry: LibreSyncConfigEntry) -> None:
    """Set up LibreSync from a config entry."""
    host = entry.data[CONF_HOST]
    client = LibreSyncClient(host)
    # The module is asked alongside the connection, so a hub that is down waits
    # no longer, and an entry added before the config flow refused these hubs
    # stops retrying.
    connected, info = await asyncio.gather(
        client.async_connect(timeout=CONNECT_TIMEOUT),
        async_query_lssdp(host),
        return_exceptions=True,
    )
    if isinstance(info, BaseException):
        await client.async_disconnect()
        raise info
    if (module := unsupported_module(info)) is not None:
        await client.async_disconnect()
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_hub",
            translation_placeholders={"host": host, "module": module},
        )
    if isinstance(connected, NotConnectedError):
        # The client disconnects again on failure, so a retry leaves nothing
        # running.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host},
        ) from connected
    if isinstance(connected, BaseException):
        raise connected

    entry.async_on_unload(client.async_disconnect)
    entry.runtime_data = client

    # The model answers a moment after the ports come up, so the device is
    # created here and kept up to date from the pushed state, before and after
    # the entity registers. The hub's serial is a module production code, not
    # the serial printed on the product, so the device does not carry it.
    assert entry.unique_id is not None
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer=MANUFACTURER,
        name=entry.title,
    )
    update_device = _device_updater(hass, device.id)
    entry.async_on_unload(client.subscribe(update_device))
    update_device(client.state)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


def _device_updater(
    hass: HomeAssistant, device_id: str
) -> Callable[[DeviceState], None]:
    """Keep the model on the device up to date."""
    seen: str | None = None

    @callback
    def update(state: DeviceState) -> None:
        nonlocal seen
        if not state.model or state.model == seen:
            return
        seen = state.model
        dr.async_get(hass).async_update_device(device_id, model=state.model)

    return update


async def async_unload_entry(hass: HomeAssistant, entry: LibreSyncConfigEntry) -> None:
    """Unload a config entry. The client disconnects after the platforms."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
