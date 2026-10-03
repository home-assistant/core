"""The LibreSync integration."""

from collections.abc import Callable

from aiolibresync import DeviceState, LibreSyncClient, NotConnectedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONNECT_TIMEOUT, DOMAIN, MANUFACTURER

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
    return True


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


async def async_unload_entry(hass: HomeAssistant, entry: LibreSyncConfigEntry) -> bool:
    """Unload a config entry. The client disconnects after the platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
