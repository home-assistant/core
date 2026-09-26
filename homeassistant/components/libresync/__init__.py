"""The LibreSync integration."""

from collections.abc import Callable
import logging
from typing import Any

from aiolibresync import DeviceState, LibreSyncClient, NotConnectedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_SERIAL, CONNECT_TIMEOUT, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type LibreSyncConfigEntry = ConfigEntry[LibreSyncClient]


async def async_setup_entry(hass: HomeAssistant, entry: LibreSyncConfigEntry) -> bool:
    """Set up LibreSync from a config entry."""
    client = LibreSyncClient(entry.data[CONF_HOST])
    try:
        # Disconnects again on failure, so a retry leaves nothing running.
        await client.async_connect(timeout=CONNECT_TIMEOUT)
    except NotConnectedError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err

    # Also on a later setup failure, which does not unload the entry.
    entry.async_on_unload(client.async_disconnect)
    entry.runtime_data = client

    # The model and the serial answer a moment after the ports come up, so the
    # device is created here and kept up to date from the pushed state, before
    # and after the entity registers.
    assert entry.unique_id is not None
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer=MANUFACTURER,
        name=entry.title,
    )
    update_device = _device_updater(hass, entry, device.id)
    entry.async_on_unload(client.subscribe(update_device))
    update_device(client.state)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _device_updater(
    hass: HomeAssistant, entry: LibreSyncConfigEntry, device_id: str
) -> Callable[[DeviceState], None]:
    """Keep the model and the serial on the device up to date.

    The entry's identity is left alone: the hub at a stored address is not
    necessarily the one that was added.
    """
    seen: tuple[str | None, str | None] | None = None

    @callback
    def update(state: DeviceState) -> None:
        nonlocal seen
        if (state.serial, state.model) == seen:
            return
        seen = (state.serial, state.model)
        known = entry.data.get(CONF_SERIAL)
        if state.serial and known and state.serial != known:
            _LOGGER.warning(
                "The hub at %s reports a different serial from the one it was "
                "added with",
                entry.data[CONF_HOST],
            )
            return
        changes: dict[str, Any] = {}
        if state.serial:
            changes["serial_number"] = state.serial
        if state.model:
            changes["model"] = state.model
        if changes:
            dr.async_get(hass).async_update_device(device_id, **changes)

    return update


async def async_unload_entry(hass: HomeAssistant, entry: LibreSyncConfigEntry) -> bool:
    """Unload a config entry. The client disconnects after the platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
