"""The Govee Light local integration."""

from errno import EADDRINUSE, EADDRNOTAVAIL, EMFILE, ENETDOWN, ENETUNREACH, ENOBUFS
from functools import partial
import logging
from typing import TYPE_CHECKING

from govee_local_api.controller import LISTENING_PORT

from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import (
    GoveeLocalApiCoordinator,
    GoveeLocalConfigEntry,
    GoveeLocalRuntimeData,
    NoListeningAddressesError,
    async_acquire_coordinator,
    async_get_legacy_entry,
    async_release_coordinator,
)

PLATFORMS: list[Platform] = [Platform.LIGHT]

# Bind errors that clear up on their own (port freed, adapter back, resources
# released); anything else needs user intervention and must not retry.
TRANSIENT_BIND_ERRNOS = frozenset(
    {EADDRINUSE, EADDRNOTAVAIL, EMFILE, ENETDOWN, ENETUNREACH, ENOBUFS}
)

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(
    hass: HomeAssistant, entry: GoveeLocalConfigEntry
) -> None:
    """Migrate a config entry to version 2."""
    if entry.version == 1:
        # Version 1 was a single entry for every lamp. Turning it into the
        # entry of one lamp needs that lamp to answer a scan, so that happens
        # during setup; the version only keeps older releases from loading
        # version 2 entries.
        hass.config_entries.async_update_entry(entry, version=2)


async def async_setup_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> None:
    """Set up Govee light local from a config entry."""

    coordinator = await _async_acquire_coordinator(hass)
    entry.async_on_unload(partial(async_release_coordinator, hass, coordinator))

    if async_get_legacy_entry(hass) is entry:
        await _async_convert_legacy_entry(hass, entry, coordinator)
    if TYPE_CHECKING:
        assert entry.unique_id is not None

    _async_adopt_registry_entries(hass, entry)

    device = await coordinator.async_wait_for_device(
        entry.unique_id, entry.data[CONF_IP_ADDRESS]
    )
    if device is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_responding",
            translation_placeholders={"ip": entry.data[CONF_IP_ADDRESS]},
        )
    entry.async_on_unload(partial(coordinator.remove_device, device))
    if device.ip != entry.data[CONF_IP_ADDRESS]:
        hass.config_entries.async_update_entry(entry, data={CONF_IP_ADDRESS: device.ip})

    entry.runtime_data = GoveeLocalRuntimeData(coordinator, device)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_acquire_coordinator(hass: HomeAssistant) -> GoveeLocalApiCoordinator:
    """Acquire the shared coordinator, mapping failures to setup errors."""
    try:
        return await async_acquire_coordinator(hass)
    except NoListeningAddressesError as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="no_listening_addresses"
        ) from ex
    except OSError as ex:
        # No address bound. Adapters are enumerated once at startup, so retry
        # rather than fail: a late or stale adapter recovers on the next attempt.
        if ex.errno == EADDRINUSE:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="port_in_use",
                translation_placeholders={"port": LISTENING_PORT},
            ) from ex
        if ex.errno in TRANSIENT_BIND_ERRNOS:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="bind_failed",
                translation_placeholders={"error": ex.strerror or str(ex)},
            ) from ex
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="bind_failed",
            translation_placeholders={"error": ex.strerror or str(ex)},
        ) from ex


async def _async_convert_legacy_entry(
    hass: HomeAssistant,
    entry: GoveeLocalConfigEntry,
    coordinator: GoveeLocalApiCoordinator,
) -> None:
    """Turn the entry for every lamp into the entry of one answering lamp.

    The other lamps it had set up get their own entry when they answer a scan.
    """
    devices = await coordinator.async_scan()
    if not devices:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="no_devices_found"
        )
    device_registry = dr.async_get(hass)
    device = next(
        (
            device
            for device in devices
            if device_registry.async_get_device_by_identifier(
                (DOMAIN, device.fingerprint), entry.entry_id
            )
        ),
        devices[0],
    )
    hass.config_entries.async_update_entry(
        entry,
        unique_id=device.fingerprint,
        title=device.sku,
        data={CONF_IP_ADDRESS: device.ip},
    )
    coordinator.async_offer_unconfigured()


@callback
def _async_adopt_registry_entries(
    hass: HomeAssistant, entry: GoveeLocalConfigEntry
) -> None:
    """Take over the lamp's device and entities from the entry it was split from."""
    if TYPE_CHECKING:
        assert entry.unique_id is not None
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for other_entry in hass.config_entries.async_entries(DOMAIN):
        if other_entry.entry_id == entry.entry_id or (
            (
                device_entry := device_registry.async_get_device_by_identifier(
                    (DOMAIN, entry.unique_id), other_entry.entry_id
                )
            )
            is None
        ):
            continue
        # Entities move first: moving the device removes the entities that
        # still belong to its previous config entry.
        for entity_entry in er.async_entries_for_device(
            entity_registry, device_entry.id, include_disabled_entities=True
        ):
            entity_registry.async_update_entity(
                entity_entry.entity_id, config_entry_id=entry.entry_id
            )
        device_registry.async_update_device(
            device_entry.id, new_config_entry_id=entry.entry_id
        )


async def async_unload_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: GoveeLocalConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing a lamp left over from the entry for every lamp."""
    return (DOMAIN, config_entry.unique_id) not in device_entry.identifiers
