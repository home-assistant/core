"""The Broadlink Magic Home integration."""

from broadlink_magic import Family, GatewaySet

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import (
    DOMAIN,
    PLATFORMS,
    device_identifier,
    family_identifier,
    gateway_identifier,
    rm_device_identifier,
)
from .coordinator import BroadLinkMagicConfigEntry, FamilyCoordinator
from .gateway_listener import async_get_gateway_listener
from .helpers import family_from_entry_data, gateways_from_entry_data


async def async_setup_entry(
    hass: HomeAssistant, entry: BroadLinkMagicConfigEntry
) -> None:
    """Set up one imported Magic Home family."""
    family = family_from_entry_data(dict(entry.data))
    try:
        listener = await async_get_gateway_listener(hass)
    except OSError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_listen",
        ) from err
    gateway_set = GatewaySet(
        family,
        gateways_from_entry_data(dict(entry.data)),
        sender=listener.registry.sendto,
    )
    coordinator = FamilyCoordinator(hass, entry, family, gateway_set)
    listener.register_gateway_set(
        entry.entry_id,
        gateway_set,
        lambda: coordinator.async_set_updated_data(gateway_set),
    )
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await _async_finish_setup(hass, entry, family, coordinator)
    except BaseException:
        await listener.async_unregister_entry(entry.entry_id)
        raise


async def _async_finish_setup(
    hass: HomeAssistant,
    entry: BroadLinkMagicConfigEntry,
    family: Family,
    coordinator: FamilyCoordinator,
) -> None:
    """Create the family registry entries and forward the platforms."""
    gateway_set = coordinator.gateway_set
    registry = dr.async_get(hass)
    family_device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, family_identifier(family.family_id))},
        manufacturer="BroadLink",
        name=family.name,
        model="Magic Home",
    )
    if family_device.area_id is None:
        default_room = next(
            (room for room in family.rooms if room.room_id == 0 and room.name),
            None,
        )
        if default_room is not None:
            area = ar.async_get(hass).async_get_or_create(default_room.name)
            family_device = (
                registry.async_update_device(family_device.id, area_id=area.id)
                or family_device
            )
    runtime_gateways = {gateway.mac: gateway for gateway in gateway_set.gateways}
    for imported_gateway in family.gateways:
        gateway = runtime_gateways.get(imported_gateway.mac)
        mac = imported_gateway.mac
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, gateway_identifier(mac))},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer="BroadLink",
            name=(gateway.name if gateway else imported_gateway.name) or "Gateway",
            model="Magic Home Gateway",
            via_device_id=family_device.id,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_cleanup_stale_registry_entries(hass, entry, family)


def _async_cleanup_stale_registry_entries(
    hass: HomeAssistant,
    entry: BroadLinkMagicConfigEntry,
    family: Family,
) -> None:
    """Remove entities and devices no longer present after a reimport."""
    base = family.family_id
    expected_entities: set[tuple[str, str]] = {
        *(
            (Platform.CLIMATE, f"{base}_{device.stable_id}")
            for device in family.climate_devices
        ),
        *(
            (Platform.CLIMATE, f"{base}_{device.stable_id}_floor_heating")
            for device in family.three_in_one_devices
        ),
    }
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if (entity.domain, entity.unique_id) not in expected_entities:
            entity_registry.async_remove(entity.entity_id)

    expected_devices = {
        family_identifier(family.family_id),
        *(gateway_identifier(gateway.mac) for gateway in family.gateways),
        *(
            (
                rm_device_identifier(device.stable_id)
                if device.is_rm_child
                else device_identifier(device.stable_id)
            )
            for device in family.climate_devices
        ),
    }
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        domain_identifiers = {
            identifier for identifier in device.identifiers if identifier[0] == DOMAIN
        }
        if domain_identifiers and not any(
            identifier[1] in expected_devices for identifier in domain_identifiers
        ):
            device_registry.async_remove_device(device.id)


async def async_unload_entry(
    hass: HomeAssistant, entry: BroadLinkMagicConfigEntry
) -> None:
    """Unload one Magic Home family."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    listener = await async_get_gateway_listener(hass)
    await listener.async_unregister_entry(entry.entry_id)
    await entry.runtime_data.gateway_set.async_close()
    await entry.runtime_data.async_shutdown()
