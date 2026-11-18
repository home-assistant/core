"""The EARN-E P1 Meter integration."""

from typing import TYPE_CHECKING

from earn_e_p1 import DEFAULT_PORT, EarnEP1Listener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_SERIAL, DOMAIN, EARN_E_P1_DATA
from .coordinator import EarnEP1Coordinator
from .models import EarnEP1Data

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EarnEP1ConfigEntry = ConfigEntry[EarnEP1Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> None:
    """Set up EARN-E P1 Meter from a config entry."""
    host = entry.data[CONF_HOST]
    serial = entry.data[CONF_SERIAL]

    data = hass.data.setdefault(EARN_E_P1_DATA, EarnEP1Data())
    async with data.lock:
        if (listener := data.listener) is None:
            listener = EarnEP1Listener()
            try:
                await listener.start()
            except OSError as err:
                raise ConfigEntryNotReady(
                    f"Cannot start UDP listener on port {DEFAULT_PORT}: {err}"
                ) from err
            data.listener = listener

        # Claim the listener under the lock, so that another entry unloading
        # while this one sets up cannot stop it from under us.
        data.entries.add(entry.entry_id)

    async def _release_listener() -> None:
        """Stop the shared listener once the last entry has released it."""
        async with data.lock:
            data.entries.discard(entry.entry_id)
            if not data.entries:
                data.listener = None
                await listener.stop()

    entry.async_on_unload(_release_listener)

    await _async_update_registries(hass, entry, serial)

    coordinator = EarnEP1Coordinator(hass, entry, host, serial, listener)
    coordinator.start()
    entry.async_on_unload(coordinator.stop)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_update_registries(
    hass: HomeAssistant, entry: EarnEP1ConfigEntry, serial: str
) -> None:
    """Move the device and entities onto the entry's meter and current dongle.

    Entries created before the equipment ID was used are keyed on the dongle
    serial until the coordinator sees the meter's equipment ID. The device
    gets the MAC of the current dongle, which drops the MAC of a swapped-out
    one; entities would only add to it.
    """
    if TYPE_CHECKING:
        assert entry.unique_id is not None
    identifier = entry.unique_id

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        device_registry.async_update_device(
            device.id,
            new_identifiers={(DOMAIN, identifier)},
            new_connections={
                connection
                for connection in device.connections
                if connection[0] != dr.CONNECTION_NETWORK_MAC
            }
            | {(dr.CONNECTION_NETWORK_MAC, dr.format_mac(serial))},
        )

    @callback
    def _migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        # The serial in the entry may already belong to a newer dongle, so
        # replace whatever identifier the unique ID starts with.
        prefix, _, key = entity_entry.unique_id.partition("_")
        if prefix == identifier:
            return None
        return {"new_unique_id": f"{identifier}_{key}"}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)


async def async_migrate_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> None:
    """Migrate an old config entry."""
    if entry.minor_version < 2:
        # The device MAC now comes from the dongle serial, which is its MAC.
        data = {**entry.data}
        data.pop(CONF_MAC, None)
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)


async def async_unload_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
