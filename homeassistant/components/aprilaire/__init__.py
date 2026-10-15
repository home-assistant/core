"""The Aprilaire integration."""

import logging

from pyaprilaire.const import Attribute

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN
from .coordinator import AprilaireConfigEntry, AprilaireCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.HUMIDIFIER,
    Platform.SELECT,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: AprilaireConfigEntry) -> None:
    """Set up a config entry for Aprilaire."""

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    coordinator = AprilaireCoordinator(hass, entry, host, port)
    await coordinator.start_listen()

    async def ready_callback(ready: bool) -> None:
        if ready:
            mac_address = format_mac(coordinator.data[Attribute.MAC_ADDRESS])

            if mac_address != entry.unique_id:
                raise ConfigEntryAuthFailed("Invalid MAC address")

            entry.runtime_data = coordinator
            entry.async_on_unload(coordinator.stop_listen)

            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

            async def _async_close(_: Event) -> None:
                coordinator.stop_listen()

            entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)
            )
        else:
            coordinator.stop_listen()

            raise ConfigEntryNotReady("Failed to wait for ready")

    await coordinator.wait_for_ready(ready_callback)


async def async_unload_entry(hass: HomeAssistant, entry: AprilaireConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


def _zero_pad_mac(mac_address: str) -> str:
    """Zero-pad each octet of a MAC address formatted by pyaprilaire < 0.10.

    Older versions of pyaprilaire dropped the leading zero of octets below
    0x10 (e.g. "b4:82:55:0:1a:5"), which format_mac passes through unchanged.
    """
    return format_mac(":".join(octet.zfill(2) for octet in mac_address.split(":")))


async def async_migrate_entry(hass: HomeAssistant, entry: AprilaireConfigEntry) -> None:
    """Migrate an Aprilaire config entry to the current version."""

    if entry.minor_version < 2:
        # pyaprilaire 0.10 zero-pads the octets of the MAC address, which is
        # used as the unique ID of the entry, its entities and its device.
        old_unique_id = entry.unique_id
        new_unique_id = _zero_pad_mac(old_unique_id) if old_unique_id else None

        if old_unique_id and new_unique_id and new_unique_id != old_unique_id:
            await _async_migrate_mac_address(hass, entry, old_unique_id, new_unique_id)
            hass.config_entries.async_update_entry(
                entry, unique_id=new_unique_id, minor_version=2
            )
        else:
            hass.config_entries.async_update_entry(entry, minor_version=2)


async def _async_migrate_mac_address(
    hass: HomeAssistant,
    entry: AprilaireConfigEntry,
    old_mac_address: str,
    new_mac_address: str,
) -> None:
    """Move the entities and device of an entry to the zero-padded MAC address."""

    entity_registry = er.async_get(hass)

    @callback
    def _update_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        if not entity_entry.unique_id.startswith(f"{old_mac_address}_"):
            return None

        new_unique_id = (
            f"{new_mac_address}{entity_entry.unique_id.removeprefix(old_mac_address)}"
        )

        if entity_registry.async_get_entity_id(
            entity_entry.domain, DOMAIN, new_unique_id
        ):
            _LOGGER.warning(
                "Cannot migrate %s to unique ID %s as it is already in use",
                entity_entry.entity_id,
                new_unique_id,
            )
            return None

        return {"new_unique_id": new_unique_id}

    await er.async_migrate_entries(hass, entry.entry_id, _update_unique_id)

    device_registry = dr.async_get(hass)
    old_connection = (dr.CONNECTION_NETWORK_MAC, old_mac_address)

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if (DOMAIN, old_mac_address) not in device_entry.identifiers:
            continue

        new_identifiers = (device_entry.identifiers - {(DOMAIN, old_mac_address)}) | {
            (DOMAIN, new_mac_address)
        }
        new_connections = device_entry.connections
        if old_connection in new_connections:
            new_connections = (new_connections - {old_connection}) | {
                (dr.CONNECTION_NETWORK_MAC, new_mac_address)
            }

        device_registry.async_update_device(
            device_entry.id,
            new_identifiers=new_identifiers,
            new_connections=new_connections,
        )
