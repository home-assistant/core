"""The Mikrotik component."""

from typing import Any

from librouteros import Api

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import (
    MikrotikConfigEntry,
    MikrotikData,
    MikrotikDataUpdateCoordinator,
    get_api,
)
from .utils import (
    interface_identifier,
    legacy_interface_identifier,
    mikrotik_config_entry_errors,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


def _call_api(data: dict[str, Any]) -> Api:
    """Call the Mikrotik API."""
    with mikrotik_config_entry_errors(during_setup=True):
        api: Api = get_api(data)
        return api


def _setup_mikrotik_data(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry, data: dict[str, Any]
) -> MikrotikData:
    """Connect to the Mikrotik API and fetch the hub details."""
    mk_data = MikrotikData(hass, config_entry, _call_api(data))
    mk_data.get_hub_details()
    return mk_data


@callback
def _async_migrate_interface_identifiers(
    hass: HomeAssistant,
    config_entry: MikrotikConfigEntry,
    coordinator: MikrotikDataUpdateCoordinator,
) -> None:
    """Scope interface unique IDs and device identifiers to the router.

    They used to be "<MAC>_<name>", which collides between routers for
    interfaces without a MAC address (e.g. WireGuard) and for the virtual MAC
    that VRRP peers share. The hub data is needed to map the old identifiers,
    so this runs on setup instead of in a config entry migration.
    """
    migrated = {
        legacy_interface_identifier(
            interface.get("mac-address"), interface["name"]
        ): interface_identifier(coordinator.interface_scope, interface["name"])
        for interface in coordinator.api.interfaces
        if interface.get("name")
    }

    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if (
            new_unique_id := migrated.get(entity_entry.unique_id)
        ) and not entity_registry.async_get_entity_id(
            entity_entry.domain, DOMAIN, new_unique_id
        ):
            entity_registry.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_unique_id
            )

    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        identifiers = {
            (domain, migrated[identifier])
            if domain == DOMAIN and identifier in migrated
            else (domain, identifier)
            for domain, identifier in device_entry.identifiers
        }
        if identifiers != device_entry.identifiers and not any(
            device_registry.async_get_device_by_identifier(
                identifier, config_entry_id=config_entry.entry_id
            )
            for identifier in identifiers - device_entry.identifiers
        ):
            device_registry.async_update_device(
                device_entry.id, new_identifiers=identifiers
            )


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> None:
    """Set up the Mikrotik component."""
    mk_data = await hass.async_add_executor_job(
        _setup_mikrotik_data, hass, config_entry, dict(config_entry.data)
    )

    coordinator = MikrotikDataUpdateCoordinator(hass, config_entry, mk_data)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    _async_migrate_interface_identifiers(hass, config_entry, coordinator)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.serial_num)},
        manufacturer=ATTR_MANUFACTURER,
        model=coordinator.model,
        name=coordinator.hostname,
        sw_version=coordinator.firmware,
    )

    @callback
    def _async_remove_stale_devices() -> None:
        """Remove interface devices the hub no longer reports."""
        known_identifiers = {(DOMAIN, coordinator.serial_num)}
        for interface in coordinator.api.interfaces:
            if name := interface.get("name"):
                known_identifiers.add(
                    (DOMAIN, interface_identifier(coordinator.interface_scope, name))
                )

        for device_entry in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            own_identifiers = {
                identifier
                for identifier in device_entry.identifiers
                if identifier[0] == DOMAIN
            }
            # device-tracker clients are linked by MAC connection only, so an
            # entry without an own identifier is never an interface device
            if own_identifiers and own_identifiers.isdisjoint(known_identifiers):
                device_registry.async_remove_device(device_entry.id)

    _async_remove_stale_devices()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_remove_stale_devices)
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
    await hass.async_add_executor_job(config_entry.runtime_data.api.api.close)
