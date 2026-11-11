"""The Broadlink integration."""

from broadlink_async.magic import Family, GatewaySet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import ConfigType

from .const import (
    BROADLINK_DATA,
    DOMAIN,
    MAGIC_PLATFORMS,
    BroadlinkData,
    is_magic_entry,
    magic_device_identifier,
    magic_family_identifier,
    magic_gateway_identifier,
    magic_rm_device_identifier,
)
from .coordinator import BroadLinkMagicConfigEntry, FamilyCoordinator
from .device import BroadlinkDevice
from .heartbeat import BroadlinkHeartbeat
from .magic_gateway_listener import async_get_gateway_listener
from .magic_helpers import family_from_entry_data, gateways_from_entry_data

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Broadlink integration."""
    hass.data[BROADLINK_DATA] = BroadlinkData()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a classic device or an imported Magic family."""
    if is_magic_entry(entry):
        await _async_setup_magic_entry(hass, entry)
        return

    data = hass.data[BROADLINK_DATA]

    device = BroadlinkDevice(hass, entry)
    if not await device.async_setup():
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        )
    if data.heartbeat is None:
        data.heartbeat = BroadlinkHeartbeat(hass)
        hass.async_create_task(data.heartbeat.async_setup())


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    if is_magic_entry(entry):
        await _async_unload_magic_entry(hass, entry)
        return

    data = hass.data[BROADLINK_DATA]

    device = data.devices.pop(entry.entry_id)
    result = await device.async_unload()

    if data.heartbeat and not data.devices:
        await data.heartbeat.async_unload()
        data.heartbeat = None

    if not result:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unload_failed",
        )


async def _async_setup_magic_entry(
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
        await _async_finish_magic_setup(hass, entry, family, coordinator)
    except BaseException:
        await listener.async_unregister_entry(entry.entry_id)
        raise


async def _async_finish_magic_setup(
    hass: HomeAssistant,
    entry: BroadLinkMagicConfigEntry,
    family: Family,
    coordinator: FamilyCoordinator,
) -> None:
    """Create the family registry entries and forward the Magic platforms."""
    gateway_set = coordinator.gateway_set
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    registry = dr.async_get(hass)
    family_device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, magic_family_identifier(family.family_id))},
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
            identifiers={(DOMAIN, magic_gateway_identifier(mac))},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer="BroadLink",
            name=(gateway.name if gateway else imported_gateway.name) or "Gateway",
            model="Magic Home Gateway",
            via_device_id=family_device.id,
        )

    await hass.config_entries.async_forward_entry_setups(entry, MAGIC_PLATFORMS)
    _async_cleanup_stale_magic_registry_entries(hass, entry, family)


def _async_cleanup_stale_magic_registry_entries(
    hass: HomeAssistant,
    entry: BroadLinkMagicConfigEntry,
    family: Family,
) -> None:
    """Remove Magic entities and devices no longer present after reimport."""
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
        *(
            (Platform.LIGHT, f"{base}_{device.stable_id}")
            for device in family.light_devices
        ),
        *(
            (Platform.SWITCH, f"{base}_{device.stable_id}_{channel}")
            for device in family.switch_devices
            for channel in range(device.channel_count)
        ),
    }
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if (
            entity.platform == DOMAIN
            and (entity.domain, entity.unique_id) not in expected_entities
        ):
            entity_registry.async_remove(entity.entity_id)

    expected_devices = {
        magic_family_identifier(family.family_id),
        *(magic_gateway_identifier(gateway.mac) for gateway in family.gateways),
        *(
            (
                magic_rm_device_identifier(device.stable_id)
                if device.is_rm_child
                else magic_device_identifier(device.stable_id)
            )
            for device in (
                *family.climate_devices,
                *family.light_devices,
                *family.switch_devices,
            )
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


async def _async_unload_magic_entry(
    hass: HomeAssistant, entry: BroadLinkMagicConfigEntry
) -> None:
    """Unload one Magic Home family."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, MAGIC_PLATFORMS)
    if hasattr(entry, "runtime_data"):
        listener = await async_get_gateway_listener(hass)
        await listener.async_unregister_entry(entry.entry_id)
        await entry.runtime_data.gateway_set.async_close()
        await entry.runtime_data.async_shutdown()
